"""Facade over the domain services; this is what QML talks to.

QML calls ``bridge.xxx`` and connects to ``bridge.yyy`` signals. The facade
keeps that surface byte-for-byte identical - the services behind it are an
implementation detail, so the QML side never has to know that scanning,
versions, configuration and settings live in different objects.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from ... import APP_VERSION
from ...paths import data_root
from ...util import log
from ..conf_model import ConfigListModel
from ..models import GameListModel, status_for
from .config import ConfigService
from .jobs import JobService
from .library import LibraryService
from .settings import SettingsService
from .versions import VersionsService


class Bridge(QObject):
    """Exposes the core operations to QML."""

    statusMessage = Signal(str, str)          # text, kind (info/ok/warn/error)
    progressChanged = Signal(float, str)      # 0..1 (negative = hide), label
    gamesReady = Signal(int)                  # row count, after a scan
    # Row keys whose DXVK state changed; QML refreshes its state counters.
    statusesReady = Signal("QVariantList")  # pyright: ignore[reportArgumentType]
    # Localized (Chinese) store name for one game.
    nameZhReady = Signal(str, str)            # key, localized name
    detected = Signal(str, str, str)          # key, direct3d, arch
    coverReady = Signal(str, str, str)        # key, card_url, round_url (§22 scheme B)
    # QVariantMap matters: a bare Python dict arrives in QML as an opaque
    # object, so payload.kind was undefined and the page silently discarded
    # every result.
    versionsReady = Signal("QVariantMap")  # pyright: ignore[reportArgumentType]  # kind / releases / installed
    localVersionsReady = Signal("QVariantMap")  # pyright: ignore[reportArgumentType]  # {"dxvk": [...], "gplasync": [...]}
    # Storage page: sizes, per-version health and orphaned install records.
    cacheStatsReady = Signal("QVariantMap")  # pyright: ignore[reportArgumentType]
    fingerprintReady = Signal(str, "QVariantMap")  # pyright: ignore[reportArgumentType]  # key / fingerprint payload
    busyChanged = Signal(bool)
    # Worker threads hand results back through this signal so every callback
    # (and therefore every model reset) runs on the interface thread. Qt drops
    # or half-applies model resets performed on another thread, which showed up
    # as views that never created a single delegate.
    taskFinished = Signal(object, object)

    # Fired when the config editor switches its editing target ("" = the shared
    # default, otherwise a game key). The page reloads the model and preview.
    configTargetChanged = Signal(str, str)  # key, display name
    # ui_lang changed at runtime: the translator was swapped and the model
    # retranslated, so the interface should re-pull derived strings (§28).
    languageChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.model = GameListModel(self)
        self.config = ConfigListModel(self)
        # The scanned library, shared by every service that needs to resolve a
        # game key to an install directory.
        self._games: dict[str, Any] = {}
        self._urls: dict[str, list[str]] = {}
        self._patched: set[str] = set()
        self._jobs = JobService(self.busyChanged.emit)
        self._library = LibraryService(self)
        self._versions = VersionsService(self)
        self._config_service = ConfigService(self)
        self._settings = SettingsService(self)

        # Signals are emitted from worker threads; these connections deliver
        # them on the interface thread because the bridge lives there.
        # statusesReady is deliberately NOT connected back into the bridge: it
        # is a one-way notification for QML (the DXVK-state counters), and a
        # self-connection would turn the emit in _apply_statuses into a loop.
        self.detected.connect(self._apply_detected)
        self.nameZhReady.connect(self._apply_name_zh)
        self.coverReady.connect(self._apply_cover)
        self.taskFinished.connect(self._run_callback)

    # -- scanning --------------------------------------------------------
    @Slot()
    def scanGames(self) -> None:
        self._library.scan_games()

    @Slot()
    def addManualGame(self) -> None:
        self._library.add_manual_game()

    @Slot(str)
    def detectGame(self, key: str) -> None:
        self._library.detect_game(key)

    @Slot(str)
    def setSort(self, key: str) -> None:  # noqa: N802 - QML naming
        """Pick a sort column; choosing the same one again flips direction."""
        self.model.set_sort(key)

    @Slot(bool)
    def setSortDescending(self, descending: bool) -> None:  # noqa: N802
        """Explicit direction, used by the 升序 / 降序 buttons."""
        self.model.set_sort_descending(descending)

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
        self._library.request_range(first, last)

    @Slot(str)
    def requestCover(self, key: str) -> None:
        self._library.request_cover(key)

    # -- versions --------------------------------------------------------
    @Slot(str, bool)
    def loadVersions(self, kind: str = "dxvk", force: bool = False) -> None:
        self._versions.load_versions(kind, force)

    @Slot(str, str, result=str)
    def releaseUrl(self, kind: str, version: str) -> str:  # noqa: N802
        return self._versions.release_url(kind, version)

    @Slot(str, str)
    def downloadVersion(self, kind: str, version: str) -> None:
        self._versions.download_version(kind, version)

    @Slot()
    def loadLocalVersions(self) -> None:
        self._versions.load_local_versions()

    @Slot(str, str)
    def removeVersion(self, kind: str, version: str) -> None:
        self._versions.remove_version(kind, version)

    # -- storage / cleanup -------------------------------------------------
    @Slot(str, bool)
    def removeDxvk(self, key: str, artifacts: bool) -> None:
        self._library.remove_dxvk(key, artifacts)

    @Slot()
    def requestCacheStats(self) -> None:
        self._versions.request_cache_stats()

    @Slot(str, bool)
    def clearCache(self, kind: str, keepUsed: bool) -> None:
        self._versions.clear_cache(kind, keepUsed)

    @Slot()
    def pruneLedger(self) -> None:
        self._versions.prune_ledger()

    # -- fingerprint / takeover -------------------------------------------
    @Slot(str)
    def requestFingerprint(self, key: str) -> None:
        self._library.request_fingerprint(key)

    @Slot(str, bool)
    def adoptDxvk(self, key: str, backupFromSystem: bool) -> None:
        self._library.adopt_dxvk(key, backupFromSystem)

    # -- install / restore -----------------------------------------------
    @Slot(str, str, str)
    def installDxvk(self, key: str, kind: str, version: str) -> None:
        self._library.install_dxvk(key, kind, version)

    @Slot(str)
    def restoreGame(self, key: str) -> None:
        self._library.restore_game(key)

    # -- configuration generator -----------------------------------------
    @Slot()
    def loadConfig(self) -> None:  # noqa: N802
        self._config_service.load_config()

    @Slot(str, bool, str)
    def setOption(self, key: str, enabled: bool, value: str) -> None:  # noqa: N802
        self._config_service.set_option(key, enabled, value)

    @Slot(str, str, str)
    def filterConfig(self, search: str, mode: str, section: str = "") -> None:  # noqa: N802
        self._config_service.filter_config(search, mode, section)

    @Slot(result=str)
    def previewConfig(self) -> str:  # noqa: N802
        return self._config_service.preview_config()

    @Slot(result=int)
    def selectedOptionCount(self) -> int:  # noqa: N802
        return self._config_service.selected_option_count()

    @Slot(result=str)
    def modifiedSummary(self) -> str:  # noqa: N802
        """Human-readable summary of modified options (§33 change summary)."""
        return self._config_service.modified_summary()

    @Slot(str)
    def resetOption(self, key: str) -> None:  # noqa: N802
        """Revert one option to default (§33 modified-list revert button)."""
        self._config_service.reset_option(key)

    @Slot(result=str)
    def importConfig(self) -> str:  # noqa: N802
        """Load an existing dxvk.conf and tick the options it contains."""
        return self._config_service.import_config()

    @Slot(result="QVariant")
    def gameOptions(self) -> Any:  # noqa: N802 - QML naming
        """Games that a dxvk.conf can be written to, for the pickers."""
        return self._config_service.game_options()

    @Slot(str, result=str)
    def writeConfToGame(self, key: str) -> str:  # noqa: N802
        """Write the generated dxvk.conf next to one game's executable."""
        return self._config_service.write_conf_to_game(key)

    @Slot()
    def copyConfig(self) -> None:  # noqa: N802
        self._config_service.copy_config()

    @Slot(result=str)
    def exportConfig(self) -> str:  # noqa: N802
        return self._config_service.export_config()

    # -- per-game config targets ------------------------------------------
    @Slot(str, str)
    def setConfigTarget(self, gameKey: str, name: str = "") -> None:  # noqa: N802
        """Point the config editor at the shared default ("") or one game."""
        self._config_service.set_config_target(gameKey, name)

    @Slot(result=str)
    def currentConfigTarget(self) -> str:  # noqa: N802
        return self._config_service.current_target()

    @Slot(result=str)
    def currentConfigTargetName(self) -> str:  # noqa: N802
        return self._config_service.current_target_name()

    @Slot(str, result=str)
    def gameConfigStatus(self, gameKey: str) -> str:  # noqa: N802
        """Compare the edited config with the dxvk.conf on disk."""
        return self._config_service.game_config_status(gameKey)

    # -- presets -----------------------------------------------------------
    @Slot(str, result=int)
    def applyPreset(self, name: str) -> int:  # noqa: N802
        """Apply a preset to the current target; returns how many options were set."""
        return self._config_service.apply_preset(name)

    @Slot(result="QVariant")
    def listPresets(self) -> Any:  # noqa: N802 - QML naming
        return self._config_service.list_presets()

    @Slot(str)
    def savePreset(self, name: str) -> None:  # noqa: N802
        self._config_service.save_preset(name)

    @Slot(str)
    def deletePreset(self, name: str) -> None:  # noqa: N802
        self._config_service.delete_preset(name)

    # -- bulk actions ------------------------------------------------------
    @Slot()
    def clearConfig(self) -> None:  # noqa: N802
        """Drop every selection of the current target."""
        self._config_service.clear_config()

    @Slot()
    def resetConfigToDefault(self) -> None:  # noqa: N802
        """Copy the shared default over the current game's own config."""
        self._config_service.reset_config_to_default()

    @Slot(str)
    def toggleSection(self, label: str) -> None:  # noqa: N802
        self._config_service.toggle_section(label)

    # -- settings and shell ----------------------------------------------
    @Slot(result=str)
    def probeLocalProxy(self) -> str:  # noqa: N802
        """Look for a proxy listening on the usual local ports."""
        return self._settings.probe_local_proxy()

    @Slot(result="QVariantList")
    def downloadSources(self) -> Any:  # noqa: N802
        """Choices for the release download source."""
        return self._settings.download_sources()

    @Slot(str)
    def setDownloadSource(self, value: str) -> None:  # noqa: N802
        self._settings.set_download_source(value)

    @Slot(result=str)
    def currentDownloadSource(self) -> str:  # noqa: N802
        return self._settings.current_download_source()

    @Slot(str, result="QVariant")
    def getSetting(self, key: str) -> Any:  # noqa: N802 - QML naming
        return self._settings.get_setting(key)

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value: Any) -> None:  # noqa: N802
        self._settings.set_setting(key, value)

    @Slot(result=str)
    def dataRoot(self) -> str:  # noqa: N802
        return str(data_root())

    @Slot(result=str)
    def appVersion(self) -> str:  # noqa: N802
        return APP_VERSION

    @Slot()
    def openDataFolder(self) -> None:
        self._settings.open_data_folder()

    @Slot(str)
    def openUrl(self, url: str) -> None:  # noqa: N802
        """Open a link in the default browser (only ever from a user click)."""
        self._settings.open_url(url)

    @Slot(result="QVariant")
    def officialLinks(self) -> Any:  # noqa: N802
        return self._settings.official_links()

    @Slot(result="QVariant")
    def credits(self) -> Any:  # noqa: N802
        """Acknowledgements, with the licence each project is used under."""
        return self._settings.credits()

    @Slot(result=str)
    def noticesText(self) -> str:  # noqa: N802
        """Full text of THIRD_PARTY_NOTICES.md for the in-app viewer."""
        return self._settings.notices_text()

    @Slot(str)
    def openFolder(self, path: str) -> None:
        self._settings.open_folder(path)

    @Slot(str)
    def copyText(self, text: str) -> None:
        self._settings.copy_text(text)

    # -- internals -------------------------------------------------------
    @property
    def _busy(self) -> bool:
        """Whether any background task is still running."""
        return self._jobs.busy

    @property
    def _detect_pending(self) -> set[str]:
        """Keys whose identification task is still in flight."""
        return self._jobs.pending("detect")

    @property
    def _config_model_data(self) -> Any:
        """The loaded dxvk.conf option model (None until it is loaded)."""
        return self._config_service.model_data

    def _refresh_one(self, game: Any) -> None:
        self._library.refresh_one(game)

    @Slot(str, str)
    def _apply_name_zh(self, key: str, name: str) -> None:
        self.model.set_name_zh(key, name)

    @Slot(str, str, str)
    def _apply_detected(self, key: str, direct3d: str, arch: str) -> None:
        self.model.update(key, direct3d=direct3d, arch=arch)

    @Slot(object, object)
    def _run_callback(self, result: Any, callback: Any) -> None:
        try:
            callback(result)
        except Exception as exc:  # noqa: BLE001
            log.warning("bridge callback failed: %s", exc)

    def _apply_cover(self, key: str, card_uri: str, round_uri: str) -> None:
        """Apply the sliced cover URLs (card + round) to the row (§22 B)."""
        updates = {}
        if card_uri:
            updates["coverCardUrl"] = card_uri
        if round_uri:
            updates["coverRoundUrl"] = round_uri
        if updates:
            self.model.update(key, **updates)

    def _apply_statuses(self, items: Any) -> None:
        parsed: list[tuple[str, bool, bool]] = []
        for item in items or []:
            try:
                key, status = item
            except (TypeError, ValueError):
                continue
            game = self._games.get(key)
            if game is None:
                continue
            # Derive the translated badge here (not in the worker) so the
            # result matches the active translator and can be rebuilt by
            # GameListModel.retranslate() on a language switch (§28).
            text, kind, patched, managed = status_for(game, status)
            self.model.update(
                key, statusText=text, statusKind=kind, _status=status, exists=game.exists
            )
            parsed.append((key, patched, managed))
        # Flags in one batch first: the wall is split into state sections,
        # and regrouping per game would rebuild the view 48 times.
        self.model.apply_state_bulk([(k, patched, managed) for k, patched, managed in parsed])
        for key, patched, _managed in parsed:
            if patched:
                self._patched.add(key)
            else:
                self._patched.discard(key)
        # The filter chips count DXVK states, so they go stale whenever a
        # single row is refreshed after an install/restore/removal.
        if parsed:
            self.statusesReady.emit([key for key, _patched, _managed in parsed])

    def _set_busy(self, value: bool) -> None:
        self._jobs.set_busy(value)

    def _submit(self, work: Any, done: Any, error_label: str | None, quiet: bool = False,
                *, pool: Any = None, on_error: Any = None) -> None:
        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 - reported to the UI
                log.warning("bridge task failed: %s: %s", error_label or "task", exc,
                            exc_info=log.isEnabledFor(10))
                if not quiet:
                    self.statusMessage.emit(f"{error_label or self.tr('操作失败')}：{exc}", "error")
                    self._set_busy(False)
                if on_error is not None:
                    # Pending-set bookkeeping must run even when the task
                    # failed, otherwise a game stays "in flight" forever.
                    self.taskFinished.emit(None, on_error)
                return
            # Emitting is thread safe and delivers on the interface thread.
            self.taskFinished.emit(result, done)

        (pool or self._jobs.pool).submit(runner)

    def shutdown(self) -> None:
        self._jobs.shutdown()
