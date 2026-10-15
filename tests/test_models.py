"""GameListModel grouping: managed / foreign (adopt) / clean sections."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from dxvk_toolkit import steam  # noqa: E402
from dxvk_toolkit.ui.models import GameListModel  # noqa: E402


def _game(folder: Path, name: str) -> steam.Game:
    return steam.game_from_folder(folder, name)


class GameListModelGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QGuiApplication.instance() or QGuiApplication(["tests"])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        # Sorting is persisted across instances; start each test from a known
        # order or one test's column click leaks into the next constructor.
        from dxvk_toolkit.paths import settings

        settings.set("games_sort", "name:asc", save=False)
        self.model = GameListModel()
        self.games = [
            _game(base / "managed", "Alpha"),
            _game(base / "foreign", "Beta"),
            _game(base / "clean", "Gamma"),
        ]
        for folder in (base / "managed", base / "foreign"):
            folder.mkdir()
        self.model.set_games(self.games)
        # Alpha: ours; Beta: foreign DXVK (patched, no record); Gamma: clean.
        self.model.apply_state_bulk([
            (self.games[0].key, True, True),
            (self.games[1].key, True, False),
        ])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_three_sections_under_all_view(self) -> None:
        self.model.apply_filter("", "", "all")
        names = [row["name"] for row in self.model._rows]
        self.assertEqual(
            names,
            ["已装 DXVK · 1", "Alpha", "已装·未接管 · 1", "Beta", "未安装 · 1", "Gamma"],
        )
        self.assertTrue(self.model._grouped)

    def test_single_section_has_no_header(self) -> None:
        # Everything managed -> one section, no heading noise.
        self.model.apply_state_bulk([
            (self.games[1].key, True, True),
            (self.games[2].key, True, True),
        ])
        self.model.apply_filter("", "", "all")
        names = [row["name"] for row in self.model._rows]
        self.assertEqual(names, ["Alpha", "Beta", "Gamma"])
        self.assertFalse(self.model._grouped)

    def test_state_sort_orders_three_tiers(self) -> None:
        self.model.set_sort("dxtk")
        keys = [row["key"] for row in self.model._rows if row.get("rowKind") != "header"]
        self.assertEqual(
            keys, [self.games[0].key, self.games[1].key, self.games[2].key]
        )


if __name__ == "__main__":
    unittest.main()
