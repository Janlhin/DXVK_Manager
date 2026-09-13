"""Python side of the QML bridge.

QML talks to this object: every slot runs blocking work on a worker thread and
reports back with a signal, so the interface thread never waits on the disk or
the network.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from .. import APP_VERSION, confbuild, confspec, covers, installer, sources, steam
from ..paths import data_root, settings
from ..util import log
from .models import ConfigListModel, GameListModel, status_for


class Bridge(QObject):
    """Exposes the core operations to QML."""

    statusMessage = Signal(str, str)          # text, kind (info/ok/warn/error)
    progressChanged = Signal(float, str)      # 0..1 (negative = hide), label
    gamesReady = Signal(int)                  # row count, after a scan
    statusesReady = Signal("QVariantList")
    # Localized (Chinese) store name for one game.
    nameZhReady = Signal(str, str)    # list of (key, text, kind)
    detected = Signal(str, str, str)          # key, direct3d, arch
    coverReady = Signal(str, str)             # key, file url
    # QVariantMap matters: a bare Python dict arrives in QML as an opaque
    # object, so payload.kind was undefined and the page silently discarded
    # every result.
    versionsReady = Signal("QVariantMap")     # kind / releases / installed
    localVersionsReady = Signal("QVariantMap")  # {"dxvk": [...], "gplasync": [...]}
    busyChanged = Signal(bool)
    # Worker threads hand results back through this signal so every callback
    # (and therefore every model reset) runs on the interface thread. Qt drops
    # or half-applies model resets performed on another thread, which showed up
    # as views that never created a single delegate.
    taskFinished = Signal(object, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.model = GameListModel(self)
        self.config = ConfigListModel(self)
        self._config_model_data: Any = None
        # Two pools: identification must not queue behind cover downloads.
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="qml-worker")
        self._detect_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qml-detect")
        # Name lookups hit the Steam store: keep them off the detection pool so
        # a slow network never delays the library scan.
        self._name_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="qml-names")
        self._games: dict[str, steam.Game] = {}
        self._urls: dict[str, list[str]] = {}
        self._cover_pending: set[str] = set()
        self._patched: set[str] = set()
        self._lock = threading.Lock()
        self._busy = False

        # Signals are emitted from worker threads; these connections deliver
        # them on the interface thread because the bridge lives there.
        self.statusesReady.connect(self._apply_statuses)
        self.detected.connect(self._apply_detected)
        self.nameZhReady.connect(self._apply_name_zh)
        self.coverReady.connect(self._apply_cover)
        self.taskFinished.connect(self._run_callback)

    # -- scanning --------------------------------------------------------
    @Slot()
    def scanGames(self) -> None:
        self._set_busy(True)
        self.statusMessage.emit("正在扫描游戏库…", "info")
        manual = list(settings.get("manual_games") or [])
        extra = list(settings.get("steam_extra_libraries") or [])

        def work() -> tuple[list[steam.Game], list[tuple[str, str, str]]]:
            found = steam.scan_steam_games(extra)
            known = {game.key for game in found}
            for entry in manual:
                if not isinstance(entry, dict):
                    continue
                game = steam.Game.from_dict(entry)
                if game.key not in known:
                    found.append(game)
                    known.add(game.key)
            statuses: list[tuple[str, str, str]] = []
            for game in found:
                if not game.exists:
                    continue
                # probe=True: DXVK installed by hand or by another tool is
                # real state too, while the ledger only knows about our own
                # installs. Results are cached per folder timestamp.
                status = installer.inspect(game.install_dir)
                text, kind = status_for(game, status)
                statuses.append((game.key, text, kind))
            return found, statuses

        def done(result: tuple[list[steam.Game], list[tuple[str, str, str]]]) -> None:
            games, statuses = result
            self._games = {game.key: game for game in games}
            self._urls = {game.key: covers.source_urls(game) for game in games}
            self.model.set_games(games)
            self._apply_statuses(statuses)
            self.gamesReady.emit(len(games))
            self.statusMessage.emit(f"发现 {len(games)} 款游戏", "ok")
            self._start_bulk_detection(games)
            self._start_name_lookup(games)
            self._set_busy(False)

        self._submit(work, done, "扫描游戏库失败")

    @Slot()
    def addManualGame(self) -> None:
        """Ask for a folder and add it to the manual library."""
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(None, "选择游戏目录（包含游戏 exe）")
        if not folder:
            return
        entries = list(settings.get("manual_games") or [])
        game = steam.game_from_folder(folder)
        if any(str(entry.get("install_dir", "")) == folder for entry in entries if isinstance(entry, dict)):
            self.statusMessage.emit("该目录已在列表中", "warn")
            return
        entries.append(game.to_dict())
        settings.set("manual_games", entries)
        self.statusMessage.emit(f"已添加 {game.name}", "ok")
        self.scanGames()

    @Slot(str)
    def detectGame(self, key: str) -> None:
        """Read the PE headers of a game to learn Direct3D and architecture."""
        game = self._games.get(key)
        if game is None or not game.exists:
            return

        def work() -> dict[str, str]:
            info = steam.describe_game(game.install_dir, persist=False)
            steam.flush_detect_cache()
            return info

        def done(info: dict[str, str]) -> None:
            direct3d = str(info.get("direct3d") or "")
            arch = str(info.get("arch") or "")
            self.model.update(key, direct3d=direct3d, arch=arch)
            self.detected.emit(key, direct3d, arch)

        self._submit(work, done, "识别 Direct3D 版本失败", pool=self._detect_pool)

    @Slot(str, str, str)
    def setFilter(self, search: str, platform: str, dxtk: str = "all") -> None:  # noqa: N802
        self.model.apply_filter(search, platform, dxtk)

    @Slot(result="QVariant")
    def dxtkCounts(self) -> Any:  # noqa: N802
        return self.model.dxtk_counts()

    @Slot(result="QVariant")
    def platformOptions(self) -> Any:  # noqa: N802
        return self.model.platform_options()

    # -- covers ----------------------------------------------------------
    @Slot(int, int)
    def requestRange(self, first: int, last: int) -> None:  # noqa: N802
        """Handle the cards the view reports as visible.

        Doing this from the view's own scroll signals is reliable; hooking the
        delegate's completion or property changes is not, because the view
        injects model roles without emitting a change the delegate can see.
        """
        if first < 0:
            first = 0
        if last < first:
            return
        for index in range(first, min(last, self.model.rowCount() - 1) + 1):
            key = self.model.key_at(index)
            if not key:
                continue
            game = self._games.get(key)
            if game is None:
                continue

            # Identification comes first and is never skipped: a cached cover
            # used to "continue" past this, so every visible row sat at
            # "识别中…" until the user clicked it.
            row = self.model.row(key) or {}
            if not row.get("direct3d"):
                self.detectGame(key)

            cover_key = covers.cover_key(game)
            try:
                if covers.original_path(cover_key).is_file():
                    if not row.get("coverUrl"):
                        self.model.update(
                            key, coverUrl=covers.original_path(cover_key).as_uri()
                        )
                    continue
            except OSError:
                pass
            self.requestCover(key)

    @Slot(str)
    def requestCover(self, key: str) -> None:
        """Download the cover for one game (key = the game's identity key)."""
        game = self._games.get(key)
        if game is None:
            return
        cover_key = covers.cover_key(game)   # never the install path
        with self._lock:
            if cover_key in self._cover_pending:
                return
            self._cover_pending.add(cover_key)
        urls = self._urls.get(key) or covers.source_urls(game)

        def work() -> str:
            if not urls:
                return ""
            if covers.download_cover(cover_key, urls):
                target = covers.original_path(cover_key)
                if target.is_file():
                    return target.as_uri()
            return ""

        def done(url: str) -> None:
            with self._lock:
                self._cover_pending.discard(key)
            if url:
                self.coverReady.emit(key, url)

        self._submit(work, done, None, quiet=True)

    @Slot(result=str)
    def coverUrlFor(self, key: str = "") -> str:  # pragma: no cover - helper for QML
        return ""

    # -- versions --------------------------------------------------------
    @Slot(str)
    def loadVersions(self, kind: str = "dxvk") -> None:
        self._set_busy(True)
        self.statusMessage.emit("正在获取版本列表…", "info")

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
            self.versionsReady.emit(payload)
            count = len(payload.get("releases") or [])
            self.statusMessage.emit(f"已获取 {count} 个版本", "ok" if count else "warn")
            self._set_busy(False)

        self._submit(work, done, "获取版本列表失败")

    @Slot(str, str)
    def downloadVersion(self, kind: str, version: str) -> None:
        self._set_busy(True)

        def work() -> str:
            releases = (
                sources.fetch_dxvk_releases() if kind == "dxvk" else sources.fetch_gplasync_releases()
            )
            match = next((item for item in releases if item.version == version), None)
            if match is None:
                raise RuntimeError(f"找不到版本 {version}")
            sources.download_release(
                match,
                progress=lambda done, total: self.progressChanged.emit(
                    (done / total) if total else 0.0, f"{done // 1048576} MB / {total // 1048576} MB"
                ),
            )
            return version

        def done(installed: str) -> None:
            self.progressChanged.emit(-1.0, "")
            self.statusMessage.emit(f"{installed} 下载完成", "ok")
            self.loadVersions(kind)
            self.localVersionsReady.emit(
                {"dxvk": sources.list_installed("dxvk"), "gplasync": sources.list_installed("gplasync")}
            )
            self._set_busy(False)

        self._submit(work, done, "下载失败")

    @Slot()
    def loadLocalVersions(self) -> None:
        self.localVersionsReady.emit(
            {"dxvk": sources.list_installed("dxvk"), "gplasync": sources.list_installed("gplasync")}
        )

    # -- install / restore -----------------------------------------------
    @Slot(str, str, str)
    def installDxvk(self, key: str, kind: str, version: str) -> None:
        game = self._games.get(key)
        if game is None:
            self.statusMessage.emit("请先选择一款游戏", "warn")
            return
        self._set_busy(True)

        def work() -> Any:
            installer.invalidate(game.install_dir)
            return installer.install(game.install_dir, kind, version)

        def done(result: Any) -> None:
            self.statusMessage.emit(result.message, "ok" if result.success else "error")
            self._refresh_one(game)
            self._set_busy(False)

        self._submit(work, done, "安装失败")

    @Slot(str)
    def restoreGame(self, key: str) -> None:
        game = self._games.get(key)
        if game is None:
            return
        self._set_busy(True)

        def work() -> Any:
            installer.invalidate(game.install_dir)
            return installer.restore(game.install_dir)

        def done(result: Any) -> None:
            self.statusMessage.emit(result.message, "ok" if result.success else "warn")
            self._refresh_one(game)
            self._set_busy(False)

        self._submit(work, done, "还原失败")

    @Slot(str)
    def removeDxvk(self, key: str) -> None:
        game = self._games.get(key)
        if game is None:
            return

        def work() -> Any:
            installer.invalidate(game.install_dir)
            return installer.remove_dxvk(game.install_dir)

        def done(removed: Any) -> None:
            self.statusMessage.emit(f"已移除 {len(removed)} 个文件", "ok" if removed else "warn")
            self._refresh_one(game)

        self._submit(work, done, "移除失败")

    def _refresh_one(self, game: steam.Game) -> None:
        def work() -> tuple[str, str, str]:
            installer.invalidate(game.install_dir)
            status = installer.inspect(game.install_dir)
            text, kind = status_for(game, status)
            return game.key, text, kind

        self._submit(work, lambda item: self._apply_statuses([item]), None, quiet=True)

    # -- configuration generator -----------------------------------------
    @Slot()
    def loadConfig(self) -> None:  # noqa: N802
        self.statusMessage.emit("正在载入 dxvk.conf 选项…", "info")

        def work() -> Any:
            return confspec.load_model()

        def done(model: Any) -> None:
            self._config_model_data = model
            self.config.set_groups(model.groups)
            stored = str(settings.get("config_mode") or "simple")
            self.config.apply_filter("", stored if stored in confspec.MODES else "simple")
            source = str(model.source_path) if model.source_path else "未找到参考文件"
            self.statusMessage.emit(
                f"共 {len(model.groups)} 个选项（{source}）", "ok" if model.groups else "warn"
            )

        self._submit(work, done, "载入配置选项失败")

    @Slot(str, bool, str)
    def setOption(self, key: str, enabled: bool, value: str) -> None:  # noqa: N802
        self.config.set_option(key, enabled, value)

    @Slot(str, str)
    def filterConfig(self, search: str, mode: str) -> None:  # noqa: N802
        self.config.apply_filter(search, mode)

    @Slot(result=str)
    def previewConfig(self) -> str:  # noqa: N802
        model = self._config_model_data
        if model is None:
            return "# 还没有载入参考文件\n"
        text = confbuild.build_conf(
            model.groups, self.config.values, section_order=model.section_order
        )
        return text

    @Slot(result=int)
    def selectedOptionCount(self) -> int:  # noqa: N802
        return len([value for value in self.config.values.values() if value not in (None, "")])

    @Slot(result=str)
    def importConfig(self) -> str:  # noqa: N802
        """Load an existing dxvk.conf and tick the options it contains."""
        from PySide6.QtWidgets import QFileDialog

        model = self._config_model_data
        if model is None:
            self.statusMessage.emit("还没有载入参考文件", "warn")
            return ""
        start_dir = str(settings.get("last_export_dir") or "")
        path, _filter = QFileDialog.getOpenFileName(
            None, "导入 dxvk.conf", start_dir, "DXVK 配置 (*.conf);;所有文件 (*)"
        )
        if not path:
            return ""
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.statusMessage.emit(f"读取失败：{exc}", "error")
            return ""
        values, unknown = confspec.parse_config_values(text, model)
        self.config.apply_values(values)
        settings.set("last_export_dir", str(Path(path).parent))
        summary = f"已从 {Path(path).name} 导入 {len(values)} 个选项"
        if unknown:
            summary += f"，另有 {len(unknown)} 个选项不在参考文件里（已忽略）"
        self.statusMessage.emit(summary, "ok")
        return summary

    @Slot()
    def copyConfig(self) -> None:  # noqa: N802
        self.copyText(self.previewConfig())

    @Slot(result=str)
    def exportConfig(self) -> str:  # noqa: N802
        from PySide6.QtWidgets import QFileDialog

        text = self.previewConfig()
        target, _filter = QFileDialog.getSaveFileName(
            None, "导出 dxvk.conf", "dxvk.conf", "DXVK 配置 (*.conf);;所有文件 (*)"
        )
        if not target:
            return ""
        try:
            Path(target).write_text(text, encoding="utf-8", newline="\r\n")
        except OSError as exc:
            self.statusMessage.emit(f"写入失败：{exc}", "error")
            return ""
        settings.set("last_export_dir", str(Path(target).parent))
        self.statusMessage.emit(f"已导出到 {target}", "ok")
        return target

    # -- settings and shell ----------------------------------------------
    @Slot(result=str)
    def probeLocalProxy(self) -> str:  # noqa: N802
        """Look for a proxy listening on the usual local ports.

        Most proxy clients in China (Clash, v2ray, sing-box) sit on one of a
        handful of ports; finding it saves the user from typing it in.
        """
        import socket

        for port in (7897, 7890, 7891, 10809, 10808, 1080, 2080, 8889, 8080):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                    pass
            except OSError:
                continue
            address = f"http://127.0.0.1:{port}"
            settings.set("proxy_url", address)
            settings.set("proxy_mode", "custom")
            self.statusMessage.emit(f"找到本地代理 {address}，已切换为自定义代理", "ok")
            return address
        self.statusMessage.emit("没有在常见端口上发现本地代理", "warn")
        return ""

    @Slot(result="QVariant")
    def downloadSources(self) -> Any:  # noqa: N802
        """Choices for the release download source."""
        options = [
            {"value": "auto", "label": "自动（优先官方，失败走镜像）"},
            {"value": "official", "label": "仅官方 GitHub"},
        ]
        for prefix in sources.MIRROR_PREFIXES:
            options.append({"value": f"mirror:{prefix.rstrip('/')}", "label": f"只用镜像 {prefix}"})
        return options

    @Slot(str)
    def setDownloadSource(self, value: str) -> None:  # noqa: N802
        settings.set("download_source", value or "auto")
        label = next(
            (item["label"] for item in self.downloadSources() if item["value"] == value),
            value,
        )
        self.statusMessage.emit(f"下载源：{label}", "ok")

    @Slot(result=str)
    def currentDownloadSource(self) -> str:  # noqa: N802
        return str(settings.get("download_source") or "auto")

    @Slot(str, result="QVariant")
    def getSetting(self, key: str) -> Any:  # noqa: N802 - QML naming
        return settings.get(key)

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:  # noqa: N802
        settings.set(key, value)

    @Slot(result=str)
    def dataRoot(self) -> str:  # noqa: N802
        return str(data_root())

    @Slot(result=str)
    def appVersion(self) -> str:  # noqa: N802
        return APP_VERSION

    @Slot()
    def openDataFolder(self) -> None:
        from ..util import open_in_file_manager

        open_in_file_manager(data_root())

    @Slot(str)
    def openUrl(self, url: str) -> None:  # noqa: N802
        """Open a link in the default browser (only ever from a user click)."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))
        log.info("opened link: %s", url)

    @Slot(result="QVariant")
    def officialLinks(self) -> Any:  # noqa: N802
        return [
            {"label": "DXVK 官方仓库", "url": "https://github.com/doitsujin/dxvk"},
            {"label": "DXVK Wiki（文档）", "url": "https://github.com/doitsujin/dxvk/wiki"},
            {"label": "DXVK 发布页", "url": "https://github.com/doitsujin/dxvk/releases"},
            {"label": "dxvk.conf 原文", "url": "https://github.com/doitsujin/dxvk/blob/master/dxvk.conf"},
            {"label": "DXVK-gplasync", "url": "https://gitlab.com/Ph42oN/dxvk-gplasync"},
            {"label": "PCGamingWiki", "url": "https://www.pcgamingwiki.com/"},
        ]

    @Slot(result="QVariant")
    def credits(self) -> Any:  # noqa: N802
        """Acknowledgements, with the licence each project is used under."""
        return [
            {
                "name": "DXVK",
                "author": "doitsujin 及贡献者",
                "license": "zlib",
                "role": "本工具下载并安装它的发布版本；选项说明来自其 dxvk.conf。",
                "url": "https://github.com/doitsujin/dxvk",
            },
            {
                "name": "DXVK-gplasync",
                "author": "Ph42oN 维护",
                "license": "随项目",
                "role": "带 async 补丁的 DXVK 分支，作为可选下载来源。",
                "url": "https://gitlab.com/Ph42oN/dxvk-gplasync",
            },
            {
                "name": "dxvk-version-mananger",
                "author": "artmakh",
                "license": "MIT",
                "role": "功能蓝本：Steam 库扫描、版本管理、DLL 备份与还原。本项目为其 Python 重写。",
                "url": "https://github.com/artmakh/dxvk-version-mananger",
            },
            {
                "name": "DXVK-Configurator",
                "author": "CamoMano",
                "license": "GPL-3.0",
                "role": "功能蓝本：从 dxvk.conf 生成配置界面。本项目独立实现，未复制其代码。",
                "url": "https://github.com/CamoMano/DXVK-Configurator",
            },
            {
                "name": "Qt for Python (PySide6)",
                "author": "Qt Company",
                "license": "LGPL-3.0",
                "role": "界面框架（QML / Qt Quick）。",
                "url": "https://www.qt.io/qt-for-python",
            },
            {
                "name": "Pillow",
                "author": "Python Imaging Library 社区",
                "license": "MIT-CMU",
                "role": "旧版封面缩略图使用；QML 版已能自行缩放，仅在命令行路径仍会用到。",
                "url": "https://python-pillow.org/",
            },
            {
                "name": "Python",
                "author": "Python Software Foundation",
                "license": "PSF",
                "role": "运行环境。",
                "url": "https://www.python.org/",
            },
            {
                "name": "数据与网络来源",
                "author": "Steam CDN / GitHub / GitLab / jsDelivr / PCGamingWiki",
                "license": "各自条款",
                "role": "封面图、发布版本列表、版本列表兜底、可选的兼容性信息。",
                "url": "https://github.com/doitsujin/dxvk",
            },
        ]

    @Slot(result=str)
    def noticesPath(self) -> str:  # noqa: N802
        from ..paths import bundle_dir

        return str(bundle_dir() / "THIRD_PARTY_NOTICES.md")

    @Slot(str)
    def openFolder(self, path: str) -> None:
        from ..util import open_in_file_manager

        target = Path(path)
        open_in_file_manager(target if target.exists() else target.parent)

    @Slot(str)
    def copyText(self, text: str) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self.statusMessage.emit("已复制到剪贴板", "ok")

    # -- internals -------------------------------------------------------
    @Slot(str, str)
    def _apply_name_zh(self, key: str, name: str) -> None:
        self.model.set_name_zh(key, name)

    @Slot(str, str, str)
    def _apply_detected(self, key: str, direct3d: str, arch: str) -> None:
        self.model.update(key, direct3d=direct3d, arch=arch)

    def _start_name_lookup(self, games: Any) -> None:
        """Attach Chinese store names so the search box understands them.

        Names are fetched once per game and cached on disk; games already in
        the cache are applied straight away without touching the network.
        """
        cached = steam.load_names()
        missing = []
        for game in games:
            appid = str(game.appid or "")
            if not appid:
                continue
            name = cached.get(appid)
            if name:
                self.nameZhReady.emit(game.key, name)
            else:
                missing.append((game, appid))
        if not missing:
            return

        def work() -> int:
            names = steam.load_names()
            done = 0
            for index, (game, appid) in enumerate(missing):
                name = steam.fetch_chinese_name(appid)
                if name:
                    names[appid] = name
                    self.nameZhReady.emit(game.key, name)
                    done += 1
                if index % 10 == 9:
                    steam.save_names()          # keep progress if we stop early
                    self.statusMessage.emit(
                        f"正在补齐中文名 {index + 1}/{len(missing)}", "muted")
                time.sleep(0.12)                # the store rate limits bursts
            steam.save_names()
            return done

        def finished(count: Any) -> None:
            if count:
                self.statusMessage.emit(f"已补齐 {count} 个中文名", "ok")

        self._submit(work, finished, None, quiet=True, pool=self._name_pool)

    def _start_bulk_detection(self, games: Any) -> None:
        """Identify every game once, off the interface thread.

        Results are cached on disk keyed by the folder timestamp, so this is a
        one-off cost per game; the visible-range requests only exist to make
        the first screen instant.
        """
        pending = [
            game
            for game in games
            if game.exists and not (self.model.row(game.key) or {}).get("direct3d")
        ]
        if not pending:
            return

        def work() -> int:
            done = 0
            for game in pending:
                try:
                    info = steam.describe_game(game.install_dir, persist=False)
                except Exception as exc:  # noqa: BLE001
                    log.debug("detection failed for %s: %s", game.install_dir, exc)
                    continue
                # The signal is queued to the interface thread, so the model
                # is only ever touched from there.
                self.detected.emit(game.key, str(info.get("direct3d") or ""),
                                   str(info.get("arch") or ""))
                done += 1
            steam.flush_detect_cache()
            return done

        def finished(count: Any) -> None:
            self.statusMessage.emit(f"已识别 {count} 款游戏的 Direct3D 版本", "ok")

        self._submit(work, finished, None, quiet=True, pool=self._detect_pool)

    @Slot(object, object)
    def _run_callback(self, result: Any, callback: Any) -> None:
        try:
            callback(result)
        except Exception as exc:  # noqa: BLE001
            log.warning("bridge callback failed: %s", exc)

    def _apply_statuses(self, items: Any) -> None:
        parsed: list[tuple[str, str, str]] = []
        for item in items or []:
            try:
                key, text, kind = item
            except (TypeError, ValueError):
                continue
            parsed.append((key, text, kind))
        # Flags in one batch first: the wall is split into 已装 / 未安装
        # sections, and regrouping per game would rebuild the view 48 times.
        self.model.apply_patched_bulk([(k, kind == "ok") for k, _text, kind in parsed])
        for key, text, kind in parsed:
            self.model.update(key, statusText=text, statusKind=kind)
            if kind == "ok":
                self._patched.add(key)
            else:
                self._patched.discard(key)

    def _apply_cover(self, key: str, url: str) -> None:
        self.model.update(key, coverUrl=url)

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit(value)

    def _submit(self, work: Any, done: Any, error_label: str | None, quiet: bool = False,
                *, pool: Any = None) -> None:
        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 - reported to the UI
                log.warning("bridge task failed: %s: %s", error_label or "task", exc,
                            exc_info=log.isEnabledFor(10))
                if not quiet:
                    self.statusMessage.emit(f"{error_label or '操作失败'}：{exc}", "error")
                    self._set_busy(False)
                return
            # Emitting is thread safe and delivers on the interface thread.
            self.taskFinished.emit(result, done)

        (pool or self._pool).submit(runner)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._detect_pool.shutdown(wait=False, cancel_futures=True)
        self._name_pool.shutdown(wait=False, cancel_futures=True)
