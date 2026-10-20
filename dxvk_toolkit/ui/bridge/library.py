"""Library domain: scanning, identification, covers, install and fingerprint."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ... import covers, fingerprint, installer, steam
from ...paths import settings
from ...util import log
from .base import BridgeService


class LibraryService(BridgeService):
    """Everything that happens around a game folder."""

    def __init__(self, host: Any) -> None:
        super().__init__(host)

    # -- scanning --------------------------------------------------------
    def scan_games(self) -> None:
        self._set_busy(True)
        self._status(self.tr("正在扫描游戏库…"), "info")
        manual = list(settings.get("manual_games") or [])
        extra = list(settings.get("steam_extra_libraries") or [])

        def work() -> tuple[list[steam.Game], list[tuple[str, installer.GameStatus]]]:
            found = steam.scan_all_games(extra)
            known = {game.key for game in found}
            for entry in manual:
                if not isinstance(entry, dict):
                    continue
                try:
                    game = steam.Game.from_dict(entry)
                except ValueError as exc:
                    log.warning("skipping invalid manual game entry: %s", exc)
                    continue
                if game.key not in known:
                    found.append(game)
                    known.add(game.key)
            statuses: list[tuple[str, installer.GameStatus]] = []
            for game in found:
                if not game.exists:
                    continue
                # probe=True: DXVK installed by hand or by another tool is
                # real state too, while the ledger only knows about our own
                # installs. Results are cached per folder timestamp.
                status = installer.inspect(game.install_dir)
                # Keep the raw status; the badge text is derived in
                # _apply_statuses so it can be re-translated on a language
                # switch (§28) without re-scanning the disk.
                statuses.append((game.key, status))
            return found, statuses

        def done(
            result: tuple[list[steam.Game], list[tuple[str, installer.GameStatus]]]
        ) -> None:
            games, statuses = result
            self._host._games = {game.key: game for game in games}
            self._host._urls = {game.key: covers.source_urls(game) for game in games}
            self._host.model.set_games(games)
            self._host._apply_statuses(statuses)
            self._host.gamesReady.emit(len(games))
            self._status(self.tr("发现 {} 款游戏").format(len(games)), "ok")
            self._start_bulk_detection(games)
            self._start_name_lookup(games)
            self._set_busy(False)

        self._submit(work, done, self.tr("扫描游戏库失败"))

    def add_manual_game(self) -> None:
        """Ask for a folder and add it to the manual library."""
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(None, self.tr("选择游戏目录（包含游戏 exe）"))
        if not folder:
            return
        entries = list(settings.get("manual_games") or [])
        game = steam.game_from_folder(folder)
        existing: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                existing.add(steam.Game.from_dict(entry).key)
            except ValueError:
                continue  # an unreadable legacy record is replaced below
        if game.key in existing:
            self._status(self.tr("该目录已在列表中"), "warn")
            return
        entries.append(game.to_dict())
        settings.set("manual_games", entries)
        self._status(self.tr("已添加 {}").format(game.name), "ok")
        self._host.scanGames()

    def detect_game(self, key: str) -> None:
        """Read the PE headers of a game to learn Direct3D and architecture.

        Scrolling re-requests the visible range on every frame, so the same
        game would otherwise be queued again and again while the first task is
        still running; the pending set collapses those duplicates.
        """
        game = self._host._games.get(key)
        if game is None or not game.exists:
            return
        if not self._claim("detect", key):
            return

        def work() -> dict[str, str]:
            info = steam.describe_game(game.install_dir, persist=False)
            steam.flush_detect_cache()
            return info

        def finish(_result: Any = None) -> None:
            self._release("detect", key)

        def done(info: dict[str, str]) -> None:
            finish()
            # Detection is finished, so an empty result becomes a sentinel:
            # "" means "not looked at yet" and the interface shows 识别中…,
            # which used to be shown forever for games without runtime DLLs.
            direct3d = str(info.get("direct3d") or "") or "Unknown"
            arch = str(info.get("arch") or "") or "—"
            self._host.model.update(key, direct3d=direct3d, arch=arch)
            self._host.detected.emit(key, direct3d, arch)

        self._submit(
            work,
            done,
            self.tr("识别 Direct3D 版本失败"),
            pool=self._host._jobs.detect_pool,
            on_error=finish,
        )

    # -- covers ----------------------------------------------------------
    def request_range(self, first: int, last: int) -> None:
        """Handle the cards the view reports as visible.

        Doing this from the view's own scroll signals is reliable; hooking the
        delegate's completion or property changes is not, because the view
        injects model roles without emitting a change the delegate can see.
        """
        if first < 0:
            first = 0
        if last < first:
            return
        for index in range(first, min(last, self._host.model.rowCount() - 1) + 1):
            key = self._host.model.key_at(index)
            if not key:
                continue
            game = self._host._games.get(key)
            if game is None:
                continue

            # Identification comes first and is never skipped: a cached cover
            # used to "continue" past this, so every visible row sat at
            # "识别中…" until the user clicked it.
            row = self._host.model.row(key) or {}
            if not row.get("direct3d"):
                self.detect_game(key)

            # Slicing is Pillow work (decode + resize); doing it here blocked
            # the interface thread once per visible card on every scroll. The
            # cover worker downloads, slices and reports back, and its pending
            # set makes repeated requests free.
            if row.get("coverCardUrl") and row.get("coverRoundUrl"):
                continue
            self.request_cover(key)

    def request_cover(self, key: str) -> None:
        """Download the cover for one game (key = the game's identity key)."""
        game = self._host._games.get(key)
        if game is None:
            return
        cover_key = covers.cover_key(game)   # never the install path
        if not self._claim("cover", cover_key):
            return
        urls = self._host._urls.get(key) or covers.source_urls(game)

        def work() -> tuple[str, str]:
            if not urls:
                return ("", "")
            card_uri = round_uri = ""
            if covers.download_cover(cover_key, urls):
                original = covers.original_path(cover_key)
                if original.is_file():
                    # Generate both rounded variants, then hand their URLs back.
                    card = covers.ensure_card(cover_key) or original
                    round_ = covers.ensure_round(cover_key) or original
                    card_uri = card.as_uri()
                    round_uri = round_.as_uri()
            return (card_uri, round_uri)

        def done(result: tuple[str, str]) -> None:
            # The pending set stores cover keys, not game keys; discarding
            # the game key left the cover pending forever, so a retry
            # after a failed download was silently skipped.
            self._release("cover", cover_key)
            card_uri, round_uri = result or ("", "")
            if card_uri or round_uri:
                self._host.coverReady.emit(key, card_uri, round_uri)

        def failed(_result: Any = None) -> None:
            self._release("cover", cover_key)

        self._submit(work, done, None, quiet=True, on_error=failed)

    # -- storage / cleanup -------------------------------------------------
    def remove_dxvk(self, key: str, artifacts: bool) -> None:
        """Remove DXVK from a game, optionally wiping conf/logs/shader cache."""
        game = self._host._games.get(key)
        if game is None:
            self._status(self.tr("请先选择一款游戏"), "warn")
            return
        self._set_busy(True)

        def work() -> Any:
            installer.invalidate(game.install_dir)
            return installer.remove_dxvk(game.install_dir, artifacts=artifacts)

        def done(removed: Any) -> None:
            message = self.tr("已移除 {} 个文件").format(len(removed))
            self._status(message, "ok")
            self.refresh_one(game)
            self._set_busy(False)

        self._submit(work, done, self.tr("移除失败"))

    # -- fingerprint / takeover -------------------------------------------
    def request_fingerprint(self, key: str) -> None:
        """Classify the DXVK DLLs sitting in a game folder (maybe foreign)."""
        game = self._host._games.get(key)
        if game is None:
            return
        self._set_busy(True)

        def work() -> Any:
            return self._fingerprint_payload(game.install_dir)

        def done(payload: Any) -> None:
            self._host.fingerprintReady.emit(key, payload)
            self._set_busy(False)

        self._submit(work, done, self.tr("指纹识别失败"))

    def adopt_dxvk(self, key: str, backup_from_system: bool) -> None:
        """Adopt a foreign DXVK installation into this tool's ledger."""
        game = self._host._games.get(key)
        if game is None:
            self._status(self.tr("请先选择一款游戏"), "warn")
            return
        self._set_busy(True)

        def work() -> Any:
            installer.invalidate(game.install_dir)
            return fingerprint.adopt(game.install_dir, backup_from_system_dirs=backup_from_system)

        def done(result: Any) -> None:
            message, _backed = result
            self._status(message, "ok")
            self.refresh_one(game)
            self._set_busy(False)

        self._submit(work, done, self.tr("接管失败"))

    def _fingerprint_payload(self, install_dir: Path) -> dict[str, Any]:
        fp = fingerprint.fingerprint_game(install_dir)
        return {
            "version": fp.version,
            "kind": fp.kind,
            "arch": fp.arch,
            "managed": fp.managed,
            "backuped": fp.backuped,
            "confPresent": fp.conf_present,
            "official": fp.official,
            "unverifiable": fp.unverifiable,
            "dllDir": fp.dll_dir,
            "dllNames": [dll.name for dll in fp.dxvk_dlls],
            "dlls": [
                {
                    "name": dll.name,
                    "arch": dll.arch,
                    "size": dll.size,
                    "sha256": dll.sha256[:16],
                    "fileDescription": dll.file_description,
                    "embeddedVersion": dll.embedded_version,
                    "matched": dll.matched,
                }
                for dll in fp.dlls
                if dll.present
            ],
        }

    # -- install / restore -----------------------------------------------
    def install_dxvk(self, key: str, kind: str, version: str) -> None:
        game = self._host._games.get(key)
        if game is None:
            self._status(self.tr("请先选择一款游戏"), "warn")
            return
        self._set_busy(True)

        def work() -> Any:
            installer.invalidate(game.install_dir)
            return installer.install(game.install_dir, kind, version)

        def done(result: Any) -> None:
            self._status(result.message, "ok" if result.success else "error")
            self.refresh_one(game)
            self._set_busy(False)

        self._submit(work, done, self.tr("安装失败"))

    def restore_game(self, key: str) -> None:
        game = self._host._games.get(key)
        if game is None:
            return
        self._set_busy(True)

        def work() -> Any:
            installer.invalidate(game.install_dir)
            return installer.restore(game.install_dir)

        def done(result: Any) -> None:
            self._status(result.message, "ok" if result.success else "warn")
            self.refresh_one(game)
            self._set_busy(False)

        self._submit(work, done, self.tr("还原失败"))

    def refresh_one(self, game: steam.Game) -> None:
        """Re-read one game's state after we changed its folder.

        The worker returns the same ``(key, GameStatus)`` pair the scan path
        produces. Handing back a pre-formatted badge tuple instead was
        silently rejected by ``_apply_statuses``, so every card kept showing
        its pre-install state until the next full scan.
        """

        def work() -> tuple[str, installer.GameStatus]:
            installer.invalidate(game.install_dir)
            return game.key, installer.inspect(game.install_dir)

        self._submit(work, lambda item: self._host._apply_statuses([item]), None, quiet=True)

    # -- helpers used after a scan ----------------------------------------
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
                self._host.nameZhReady.emit(game.key, name)
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
                    self._host.nameZhReady.emit(game.key, name)
                    done += 1
                if index % 10 == 9:
                    steam.save_names()          # keep progress if we stop early
                    self._status(
                        self.tr("正在补齐中文名 {}/{}").format(index + 1, len(missing)), "muted"
                    )
                time.sleep(0.12)                # the store rate limits bursts
            steam.save_names()
            return done

        def finished(count: Any) -> None:
            if count:
                self._status(self.tr("已补齐 {} 个中文名").format(count), "ok")

        self._submit(work, finished, None, quiet=True, pool=self._host._jobs.name_pool)

    def _start_bulk_detection(self, games: Any) -> None:
        """Identify every game once, off the interface thread.

        Results are cached on disk keyed by the folder timestamp, so this is a
        one-off cost per game; the visible-range requests only exist to make
        the first screen instant.
        """
        pending = [
            game
            for game in games
            if game.exists and not (self._host.model.row(game.key) or {}).get("direct3d")
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
                self._host.detected.emit(game.key,
                                         str(info.get("direct3d") or "") or "Unknown",
                                         str(info.get("arch") or "") or "—")
                done += 1
            steam.flush_detect_cache()
            return done

        def finished(count: Any) -> None:
            self._status(self.tr("已识别 {} 款游戏的 Direct3D 版本").format(count), "ok")

        self._submit(work, finished, None, quiet=True, pool=self._host._jobs.detect_pool)
