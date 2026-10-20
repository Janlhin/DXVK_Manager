"""The facade must stay a drop-in replacement for the old monolithic bridge.

QML calls ``bridge.xxx`` and connects to ``bridge.yyy``; the split into domain
services is an implementation detail. These tests pin the contract:

* every slot the QML side uses still exists with the same signature,
* every signal still exists with the same parameter count,
* the internals the tests (and future code) rely on are still reachable.
"""

from __future__ import annotations

import unittest

# The CI gate installs requirements-dev.txt only; PySide6 is a runtime
# dependency of the GUI and is absent there. Skipping keeps the suite
# runnable in both environments instead of failing collection on the Linux
# runner.
try:
    from PySide6.QtCore import QMetaMethod  # noqa: E402

    HAS_QT = True
except ImportError:  # pragma: no cover - exercised on the CI runner
    # The names stay unbound on purpose: every class that touches them is
    # skipped below, and binding them to None would turn the skipped code into
    # a static "None has no attribute" error.
    HAS_QT = False

requires_qt = unittest.skipUnless(HAS_QT, "PySide6 is not installed")

# Slots the QML side calls. Listed explicitly so a rename cannot slip through
# unnoticed: the UI would simply stop working at runtime.
QML_SLOTS: dict[str, int] = {
    "addManualGame": 0,
    "adoptDxvk": 2,
    "appVersion": 0,
    "applyPreset": 1,
    "clearCache": 2,
    "clearConfig": 0,
    "copyConfig": 0,
    "copyText": 1,
    "credits": 0,
    "currentDownloadSource": 0,
    "dataRoot": 0,
    "downloadSources": 0,
    "downloadVersion": 2,
    "dxtkCounts": 0,
    "exportConfig": 0,
    "filterConfig": 3,
    "gameConfigStatus": 1,
    "gameOptions": 0,
    "getSetting": 1,
    "importConfig": 0,
    "installDxvk": 3,
    "listPresets": 0,
    "loadConfig": 0,
    "loadLocalVersions": 0,
    "loadVersions": 2,
    "noticesText": 0,
    "officialLinks": 0,
    "openDataFolder": 0,
    "openFolder": 1,
    "openUrl": 1,
    "platformOptions": 0,
    "previewConfig": 0,
    "probeLocalProxy": 0,
    "pruneLedger": 0,
    "releaseUrl": 2,
    "removeDxvk": 2,
    "removeVersion": 2,
    "requestCacheStats": 0,
    "requestFingerprint": 1,
    "requestRange": 2,
    "resetConfigToDefault": 0,
    "restoreGame": 1,
    "savePreset": 1,
    "scanGames": 0,
    "selectedOptionCount": 0,
    "setConfigTarget": 2,
    "setDownloadSource": 1,
    "setFilter": 3,
    "setOption": 3,
    "setSetting": 2,
    "setSort": 1,
    "setSortDescending": 1,
    "toggleSection": 1,
    "writeConfToGame": 1,
}

# Signals QML connects to, with their parameter count.
QML_SIGNALS: dict[str, int] = {
    "busyChanged": 1,
    "cacheStatsReady": 1,
    "configTargetChanged": 2,
    "coverReady": 3,
    "detected": 3,
    "fingerprintReady": 2,
    "gamesReady": 1,
    "languageChanged": 0,
    "localVersionsReady": 1,
    "nameZhReady": 2,
    "progressChanged": 2,
    "statusMessage": 2,
    "statusesReady": 1,
    "taskFinished": 2,
    "versionsReady": 1,
}


@requires_qt
class BridgeContractTests(unittest.TestCase):
    """The QML-facing surface must not change when the internals move."""

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtGui import QGuiApplication as _App

        cls._app = _App.instance() or _App(["tests"])

    def setUp(self) -> None:
        from dxvk_toolkit.ui.bridge import Bridge

        self.bridge = Bridge()
        self.addCleanup(self.bridge.shutdown)

    def test_every_qml_slot_exists_with_the_right_arity(self) -> None:
        meta = self.bridge.metaObject()
        for name, arity in QML_SLOTS.items():
            with self.subTest(slot=name):
                self.assertTrue(
                    hasattr(self.bridge, name), f"bridge.{name} disappeared"
                )
                index = meta.indexOfSlot(f"{name}({','.join(['QVariant'] * arity)})")
                # PySide registers the slot with concrete type names, so fall
                # back to a name-only lookup when the exact signature differs.
                if index < 0:
                    index = meta.indexOfMethod(f"{name}({','.join(['QVariant'] * arity)})")
                if index < 0:
                    methods = [
                        meta.method(i)
                        for i in range(meta.methodCount())
                        if meta.method(i).name() == name
                    ]
                    self.assertTrue(
                        methods, f"bridge.{name} is not a registered slot"
                    )
                    self.assertEqual(
                        len(methods[0].parameterTypes()),
                        arity,
                        f"bridge.{name} changed its arity",
                    )
                else:
                    self.assertEqual(
                        len(meta.method(index).parameterTypes()),
                        arity,
                        f"bridge.{name} changed its arity",
                    )

    def test_every_qml_signal_exists_with_the_right_arity(self) -> None:
        meta = self.bridge.metaObject()
        for name, arity in QML_SIGNALS.items():
            with self.subTest(signal=name):
                self.assertTrue(
                    hasattr(self.bridge, name), f"bridge.{name} disappeared"
                )
                signals = [
                    meta.method(i)
                    for i in range(meta.methodCount())
                    if meta.method(i).name() == name
                    and meta.method(i).methodType() == QMetaMethod.MethodType.Signal
                ]
                self.assertTrue(signals, f"bridge.{name} is not a signal")
                self.assertEqual(
                    len(signals[0].parameterTypes()),
                    arity,
                    f"bridge.{name} changed its arity",
                )

    def test_models_are_still_exposed_for_the_context_properties(self) -> None:
        self.assertIsNotNone(self.bridge.model)
        self.assertIsNotNone(self.bridge.config)

    def test_busy_counter_and_pending_sets_are_reachable(self) -> None:
        self.bridge._set_busy(True)
        self.assertTrue(self.bridge._busy)
        self.bridge._set_busy(False)
        self.assertFalse(self.bridge._busy)
        self.assertEqual(self.bridge._detect_pending, set())

    def test_translation_context_survived_the_split(self) -> None:
        """The catalogue stores the Python strings under the "Bridge" context."""
        from PySide6.QtCore import QCoreApplication

        source = "正在扫描游戏库…"
        self.assertEqual(
            QCoreApplication.translate("Bridge", source),
            source,
            "the source string must survive unchanged",
        )

    def test_services_are_wired_to_the_facade(self) -> None:
        self.assertIsNotNone(self.bridge._library)
        self.assertIsNotNone(self.bridge._versions)
        self.assertIsNotNone(self.bridge._config_service)
        self.assertIsNotNone(self.bridge._settings)
        self.assertIs(self.bridge._library._host, self.bridge)


@requires_qt
class BridgeServiceBaseTests(unittest.TestCase):
    """The shared helpers of the service base class."""

    def test_tr_uses_the_shared_bridge_context(self) -> None:
        from PySide6.QtCore import QCoreApplication

        from dxvk_toolkit.ui.bridge.base import TRANSLATION_CONTEXT, BridgeService

        self.assertEqual(TRANSLATION_CONTEXT, "Bridge")
        service = BridgeService(host=None)  # type: ignore[arg-type]
        self.assertEqual(
            service.tr("正在扫描游戏库…"),
            QCoreApplication.translate("Bridge", "正在扫描游戏库…"),
        )


if __name__ == "__main__":
    unittest.main()
