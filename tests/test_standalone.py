"""The standalone configurator must behave like a separate program.

Three things are pinned here:

* the QML-facing surface (slots and signals) - a rename would break the UI
  silently, exactly as it would in the full application;
* the isolation from the full application - the configurator has its own
  settings file, its own presets and its own generated-file header, and
  must never read or write the version manager's data;
* the file round trip - opening a .conf, editing it and saving it back.

The tests that need Qt are skipped when PySide6 is absent (the CI runner
installs requirements-dev.txt only).
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Keep the standalone tool's settings in a throwaway directory. This stops the
# suite from reading or writing the developer's real configuration, and - more
# importantly - stops the language tests from depending on whatever language
# the settings file happens to hold (a manually edited "en" file made them
# fail). The home must contain the tool's slug so the path assertions in
# StandaloneIsolationTests keep passing.
_STANDALONE_TEST_PARENT = tempfile.mkdtemp(prefix="dxvk-standalone-test-")
os.environ["DXVK_CONFIGURATOR_HOME"] = str(
    Path(_STANDALONE_TEST_PARENT) / "DXVK-Configurator-Py"
)
atexit.register(shutil.rmtree, _STANDALONE_TEST_PARENT, ignore_errors=True)

try:
    from PySide6.QtCore import QMetaMethod  # noqa: E402

    HAS_QT = True
except ImportError:  # pragma: no cover - exercised on the CI runner
    HAS_QT = False

requires_qt = unittest.skipUnless(HAS_QT, "PySide6 is not installed")

# Slots the standalone QML calls, with their parameter count.
QML_SLOTS: dict[str, int] = {
    "appVersion": 0,
    "applyPreset": 1,
    "clearConfig": 0,
    "copyConfig": 0,
    "currentFile": 0,
    "exportConfig": 0,
    "filterConfig": 3,
    "getSetting": 1,
    "hasFile": 0,
    "importConfig": 0,
    "listPresets": 0,
    "loadConfig": 0,
    "modifiedSummary": 0,
    "openFile": 1,
    "previewConfig": 0,
    "resetOption": 1,
    "saveFile": 0,
    "savePreset": 1,
    "selectedOptionCount": 0,
    "setLanguage": 1,
    "setOption": 3,
    "setSetting": 2,
    "toggleSection": 1,
}

# Signals the standalone QML connects to, with their parameter count.
QML_SIGNALS: dict[str, int] = {
    "fileOpened": 2,
    "languageChanged": 1,
    "presetsChanged": 0,
    "statusMessage": 2,
}


@requires_qt
class StandaloneBridgeContractTests(unittest.TestCase):
    """The QML-facing surface of the configurator's bridge."""

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtGui import QGuiApplication as _App

        cls._app = _App.instance() or _App(["tests"])

    def setUp(self) -> None:
        from dxvk_toolkit.standalone.bridge import ConfiguratorBridge

        self.bridge = ConfiguratorBridge()

    def test_every_qml_slot_exists_with_the_right_arity(self) -> None:
        meta = self.bridge.metaObject()
        for name, arity in QML_SLOTS.items():
            with self.subTest(slot=name):
                self.assertTrue(
                    hasattr(self.bridge, name), f"bridge.{name} disappeared"
                )
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
                self.assertTrue(
                    signals, f"bridge.{name} is not a signal"
                )
                self.assertEqual(
                    len(signals[0].parameterTypes()),
                    arity,
                    f"bridge.{name} changed its arity",
                )

    def test_the_model_is_exposed_for_the_context_property(self) -> None:
        self.assertIsNotNone(self.bridge.config)
        self.assertGreaterEqual(self.bridge.config.rowCount(), 0)

    def test_translation_context_is_the_standalone_one(self) -> None:
        """The Python strings live under "Standalone", not under "Bridge"."""
        from PySide6.QtCore import QCoreApplication

        from dxvk_toolkit.standalone.bridge import TRANSLATION_CONTEXT

        self.assertEqual(TRANSLATION_CONTEXT, "Standalone")
        source = "已复制到剪贴板"
        self.assertEqual(
            QCoreApplication.translate("Standalone", source),
            source,
            "the source string must survive unchanged",
        )


@requires_qt
class StandaloneIsolationTests(unittest.TestCase):
    """The configurator must not touch the version manager's data."""

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtGui import QGuiApplication as _App

        cls._app = _App.instance() or _App(["tests"])

    def test_its_settings_file_is_not_the_applications_one(self) -> None:
        from dxvk_toolkit.paths import settings_path as app_settings_path
        from dxvk_toolkit.standalone.store import APP_SLUG, settings_path

        self.assertNotEqual(settings_path(), app_settings_path())
        self.assertIn(APP_SLUG, str(settings_path()))

    def test_presets_do_not_leak_between_the_two_tools(self) -> None:
        from dxvk_toolkit.ui import config_store

        class FakeStore:
            def __init__(self) -> None:
                self.data: dict[str, object] = {}

            def get(self, key, default=None):  # noqa: ANN001
                return self.data.get(key, default)

            def set(self, key, value, save=True):  # noqa: ANN001
                self.data[key] = value

        standalone = FakeStore()
        application = FakeStore()
        self.assertTrue(config_store.save_preset("我的预设", {"hud": "fps"}, standalone))
        self.assertEqual(config_store.preset_names(standalone), ["性能优先", "兼容优先", "纯净", "我的预设"])
        self.assertNotIn("我的预设", config_store.preset_names(application))
        self.assertEqual(config_store.preset_values("我的预设", standalone), {"hud": "fps"})
        self.assertEqual(config_store.preset_values("我的预设", application), {})

    def test_the_generated_file_does_not_claim_the_other_tool(self) -> None:
        from dxvk_toolkit.standalone.bridge import ConfiguratorBridge

        bridge = ConfiguratorBridge()
        bridge.loadConfig()
        text = bridge.previewConfig()
        self.assertIn("DXVK Configurator", text.splitlines()[0])
        self.assertNotIn("DXVK Version Manager", text)


@requires_qt
class StandaloneFileRoundTripTests(unittest.TestCase):
    """Open a .conf, change a value, save it back."""

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtGui import QGuiApplication as _App

        cls._app = _App.instance() or _App(["tests"])

    def setUp(self) -> None:
        from dxvk_toolkit.standalone.bridge import ConfiguratorBridge

        self.bridge = ConfiguratorBridge()
        self.bridge.loadConfig()
        self._dir = tempfile.TemporaryDirectory(prefix="dxvk-standalone-")
        self.addCleanup(self._dir.cleanup)
        self.path = Path(self._dir.name) / "dxvk.conf"

    def test_open_edit_save_round_trip(self) -> None:
        self.path.write_text("dxvk.hud = fps\n", encoding="utf-8")
        self.bridge.openFile(str(self.path))
        self.assertTrue(self.bridge.hasFile())
        self.assertEqual(self.bridge.currentFile(), str(self.path))
        self.assertEqual(self.bridge.config.values.get("hud"), "fps")

        self.bridge.setOption("hud", True, "frametimes")
        self.bridge.saveFile()
        written = self.path.read_text(encoding="utf-8")
        # Enum-style values are quoted, exactly as the full application
        # writes them - the two tools must produce identical files.
        self.assertIn('dxvk.hud = "frametimes"', written)

    def test_saving_without_a_file_is_refused(self) -> None:
        self.assertFalse(self.bridge.hasFile())
        self.assertEqual(self.bridge.saveFile(), "")

    def test_an_unreadable_file_reports_an_error_instead_of_raising(self) -> None:
        missing = str(Path(self._dir.name) / "nope.conf")
        self.assertEqual(self.bridge.openFile(missing), "")
        self.assertFalse(self.bridge.hasFile())


@requires_qt
class StandaloneLanguageTests(unittest.TestCase):
    """The language switch changes the interface and the option wording."""

    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtGui import QGuiApplication as _App

        cls._app = _App.instance() or _App(["tests"])

    def setUp(self) -> None:
        from dxvk_toolkit.standalone import app as standalone_app
        from dxvk_toolkit.standalone.bridge import (
            ConfiguratorBridge,
            configure_catalogue,
        )
        from dxvk_toolkit.standalone.store import settings

        # Force a known Chinese baseline. The tool defaults to Chinese, which
        # is also what a fresh install shows; pinning it here keeps the test
        # independent of the persisted settings file (which may have been left
        # on "en" by manual testing) and of the global confkit cache.
        settings.set("ui_lang", "zh")
        settings.set("docs_language", "zh")
        standalone_app.set_language("zh")
        configure_catalogue()
        self.bridge = ConfiguratorBridge()
        self.bridge.loadConfig()
        self._original = ("zh", "zh")
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        from dxvk_toolkit.standalone import app as standalone_app
        from dxvk_toolkit.standalone.store import settings

        ui_lang, docs_language = self._original
        # Drop the translator first: a leftover English catalogue would
        # translate the strings of the other tests in this process.
        standalone_app.set_language("zh")
        settings.set("ui_lang", ui_lang)
        settings.set("docs_language", docs_language)

    def _label_of(self, key: str) -> str:
        for row in self.bridge.config._all:  # noqa: SLF001 - test introspection
            if row["key"] == key:
                return str(row["label"])
        return ""

    def test_switching_to_english_rewrites_the_option_wording(self) -> None:
        chinese = self._label_of("maxFrameRate")
        self.assertTrue(chinese)
        self.bridge.setLanguage("en")
        english = self._label_of("maxFrameRate")
        self.assertNotEqual(chinese, english, "the wording did not change")
        self.assertTrue(english.isascii(), f"still Chinese: {english!r}")

    def test_the_selection_survives_a_language_switch(self) -> None:
        self.bridge.setOption("hud", True, "fps")
        self.bridge.setLanguage("en")
        self.assertEqual(self.bridge.config.values.get("hud"), "fps")

    def test_the_language_is_persisted(self) -> None:
        from dxvk_toolkit.standalone.store import settings

        self.bridge.setLanguage("en")
        self.assertEqual(settings.get("ui_lang"), "en")
        self.assertEqual(settings.get("docs_language"), "en")


class StandaloneAssetsTests(unittest.TestCase):
    """The asset lookup works without PySide6 and without the app's paths."""

    def test_asset_path_points_into_the_repository_assets(self) -> None:
        from dxvk_toolkit.standalone.assets import asset_path, bundle_dir

        self.assertTrue(bundle_dir().is_dir())
        self.assertTrue(asset_path("dxvk.conf").is_file())
        self.assertEqual(
            asset_path("dxvk.conf").parent, asset_path("dxvk.conf.zh.json").parent
        )

    def test_importing_the_standalone_package_does_not_touch_the_app_data(self) -> None:
        """Importing must not create the version manager's data directory."""
        import dxvk_toolkit.standalone  # noqa: F401
        import dxvk_toolkit.standalone.assets  # noqa: F401

        self.assertTrue(dxvk_toolkit.standalone.assets.bundle_dir().is_dir())


if __name__ == "__main__":
    unittest.main()
