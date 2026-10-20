"""Versions domain: release lists, downloads, deletion and cache cleanup."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ... import fingerprint, net, sources
from ...paths import ledger
from .base import BridgeService


class VersionsService(BridgeService):
    """Everything about DXVK / DXVK-GPLAsync releases and their caches."""

    # Refreshed in the background once the cached list is older than this.
    CACHE_TTL_SECONDS = 6 * 3600

    def load_versions(self, kind: str, force: bool = False) -> None:
        """Show the cached list at once, then refresh it when it is stale.

        Switching between 官方 DXVK and DXVK-GPLAsync used to leave the list
        empty until 刷新列表 was pressed; now the cache appears immediately and
        a stale one is refreshed silently.

        The Python defaults only apply to Python callers. The Qt meta-object
        system cannot see them, so every QML caller must pass BOTH arguments -
        a one-argument call is rejected with "Error: Insufficient arguments"
        and the slot silently never runs (that was the "共 0 个可下载版本"
        bug in the game dialog).
        """
        cached = sources.cached_releases(kind)
        if cached and not force:
            self._host.versionsReady.emit(
                {
                    "kind": kind,
                    "releases": [release.to_dict() for release in cached],
                    "installed": sources.list_installed(kind),
                    "cached": True,
                }
            )

        if not force and cached and sources.cache_age(kind) < self.CACHE_TTL_SECONDS:
            return
        if net.offline():
            if not cached:
                self._status(self.tr("离线模式：本地还没有版本缓存"), "warn")
            else:
                self._status(self.tr("离线模式：使用本地版本缓存"), "info")
            return
        if force:
            self._status(self.tr("正在强制刷新版本列表…"), "info")

        self._set_busy(True)

        def work() -> dict[str, Any]:
            releases = (
                sources.fetch_dxvk_releases() if kind == "dxvk" else sources.fetch_gplasync_releases()
            )
            return {
                "kind": kind,
                "releases": [release.to_dict() for release in releases],
                "installed": sources.list_installed(kind),
            }

        def done(payload: dict[str, Any]) -> None:
            self._host.versionsReady.emit(payload)
            count = len(payload.get("releases") or [])
            self._status(self.tr("已获取 {} 个版本").format(count), "ok" if count else "warn")
            self._set_busy(False)

        self._submit(work, done, self.tr("获取版本列表失败"))

    def release_url(self, kind: str, version: str) -> str:
        """Upstream page for one version, for the detail panel's link."""
        if kind == "gplasync":
            return "https://gitlab.com/Ph42oN/dxvk-gplasync/-/releases"
        return f"https://github.com/doitsujin/dxvk/releases/tag/{version}"

    def download_version(self, kind: str, version: str) -> None:
        self._set_busy(True)

        def work() -> str:
            releases = (
                sources.fetch_dxvk_releases() if kind == "dxvk" else sources.fetch_gplasync_releases()
            )
            match = next((item for item in releases if item.version == version), None)
            if match is None:
                raise RuntimeError(self.tr("找不到版本 {}").format(version))
            sources.download_release(
                match,
                progress=lambda done, total: self._progress(
                    (done / total) if total else 0.0, f"{done // 1048576} MB / {total // 1048576} MB"
                ),
            )
            return version

        def done(installed: str) -> None:
            self._progress(-1.0, "")
            self._status(self.tr("{} 下载完成").format(installed), "ok")
            fingerprint.forget_cache_index()
            self.load_versions(kind)
            self._host.localVersionsReady.emit(
                {"dxvk": sources.list_installed("dxvk"), "gplasync": sources.list_installed("gplasync")}
            )
            self._set_busy(False)

        self._submit(work, done, self.tr("下载失败"))

    def load_local_versions(self) -> None:
        self._host.localVersionsReady.emit(
            {"dxvk": sources.list_installed("dxvk"), "gplasync": sources.list_installed("gplasync")}
        )

    def remove_version(self, kind: str, version: str) -> None:
        """Delete one downloaded version from the local cache."""
        self._set_busy(True)

        def work() -> str:
            if not sources.is_installed(kind, version):
                raise RuntimeError(self.tr("{} 不在本地，无需删除").format(version))
            sources.remove_version(kind, version)
            return version

        def done(removed: str) -> None:
            self._status(self.tr("已删除 {}").format(removed), "ok")
            fingerprint.forget_cache_index()
            self.load_versions(kind)
            self._host.localVersionsReady.emit(
                {"dxvk": sources.list_installed("dxvk"), "gplasync": sources.list_installed("gplasync")}
            )
            self._set_busy(False)

        self._submit(work, done, self.tr("删除失败"))

    # -- storage / cleanup -------------------------------------------------
    def request_cache_stats(self) -> None:
        """Sizes and per-version health of both caches, plus dead records."""
        self._set_busy(True)

        def work() -> Any:
            payload: dict[str, Any] = {}
            for kind in ("dxvk", "gplasync"):
                payload[kind] = sources.cache_stats(kind)
            payload["orphans"] = [
                str(entry.get("install_dir") or key)
                for key, entry in ledger.all().items()
                if not Path(str(entry.get("install_dir") or key)).is_dir()
            ]
            return payload

        def done(stats: Any) -> None:
            self._host.cacheStatsReady.emit(stats)
            self._set_busy(False)

        self._submit(work, done, self.tr("读取缓存统计失败"))

    def clear_cache(self, kind: str, keep_used: bool) -> None:
        """Wipe a download cache; versions some game runs on can survive."""
        self._set_busy(True)

        def work() -> Any:
            removed = sources.clear_cache(kind, keep_used=keep_used)
            fingerprint.forget_cache_index()
            return removed

        def done(removed: Any) -> None:
            if removed:
                self._status(
                    self.tr("已清理 {} 个缓存版本").format(len(removed)), "ok"
                )
            else:
                self._status(self.tr("没有可清理的缓存版本"), "warn")
            self.load_local_versions()
            self.request_cache_stats()
            self._set_busy(False)

        self._submit(work, done, self.tr("清理缓存失败"))

    def prune_ledger(self) -> None:
        """Forget install records whose game folder no longer exists."""
        self._set_busy(True)

        def work() -> Any:
            return ledger.prune_missing()

        def done(dropped: Any) -> None:
            if dropped:
                self._status(
                    self.tr("已清理 {} 条失效的安装记录").format(len(dropped)), "ok"
                )
            else:
                self._status(self.tr("没有失效的安装记录"), "warn")
            self.request_cache_stats()
            self._set_busy(False)

        self._submit(work, done, self.tr("清理记录失败"))
