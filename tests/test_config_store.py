"""Preset and per-target config storage rules (no Qt required)."""

from __future__ import annotations

import unittest

from dxvk_toolkit.paths import settings
from dxvk_toolkit.ui import config_store


class ConfigStoreTests(unittest.TestCase):
    """The shapes written to settings.json, independent of the QML bridge."""

    def setUp(self) -> None:
        # settings is a process-wide singleton; snapshot and restore the keys
        # this module touches so other tests keep a clean slate.
        self._saved = settings.as_dict()
        settings.set("config_presets", {}, save=False)
        settings.set("config_default", {}, save=False)
        settings.set(config_store.store_key("d:/game"), {}, save=False)

    def tearDown(self) -> None:
        for key in ("config_presets", "config_default", config_store.store_key("d:/game")):
            if key in self._saved:
                settings.set(key, self._saved[key], save=False)
            else:
                settings.set(key, None, save=False)

    def test_builtin_names_cannot_be_overwritten(self) -> None:
        for name in ("性能优先", "兼容优先", config_store.PURE_PRESET):
            self.assertTrue(config_store.is_builtin(name))
            self.assertFalse(config_store.save_preset(name, {"hud": "fps"}))
        self.assertEqual(config_store.custom_presets(), {})

    def test_custom_preset_round_trip(self) -> None:
        self.assertTrue(config_store.save_preset("我的预设", {"hud": "fps", "tearFree": False}))
        self.assertEqual(
            config_store.preset_values("我的预设"), {"hud": "fps", "tearFree": False}
        )
        self.assertIn("我的预设", config_store.preset_names())
        self.assertTrue(config_store.delete_preset("我的预设"))
        self.assertFalse(config_store.delete_preset("我的预设"))
        self.assertEqual(config_store.preset_values("我的预设"), {})

    def test_pure_is_a_name_not_a_table(self) -> None:
        self.assertNotIn(config_store.PURE_PRESET, config_store.BUILTIN_PRESETS)
        self.assertTrue(config_store.is_builtin(config_store.PURE_PRESET))

    def test_targets_do_not_share_values(self) -> None:
        config_store.persist_target_values("", {"hud": "fps"})
        config_store.persist_target_values("d:/game", {"hud": "frametimes"})
        self.assertEqual(config_store.load_target_values("")["hud"], "fps")
        self.assertEqual(config_store.load_target_values("d:/game")["hud"], "frametimes")
        # The default snapshot is copied, not aliased: editing one target must
        # never leak into the other (or into the shared default).
        values = config_store.load_target_values("d:/game")
        values["hud"] = "fps"
        self.assertEqual(config_store.load_target_values("d:/game")["hud"], "frametimes")

    def test_unknown_target_is_empty(self) -> None:
        self.assertEqual(config_store.load_target_values("d:/nope"), {})


if __name__ == "__main__":
    unittest.main()
