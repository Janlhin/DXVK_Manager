"""GameListModel grouping: managed / foreign (adopt) / clean sections."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never touch the real user profile: the model constructor reads settings and
# a sort click persists one.
os.environ.setdefault(
    "DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-model-tests")
)

# The CI gate installs requirements-dev.txt only; PySide6 is a runtime
# dependency of the GUI and is absent there. Skipping keeps the suite runnable
# in both environments instead of failing collection on the Linux runner.
try:
    from PySide6.QtCore import QTranslator  # noqa: E402
    from PySide6.QtGui import QGuiApplication  # noqa: E402

    from dxvk_toolkit.ui.models import GameListModel  # noqa: E402

    HAS_QT = True
except ImportError:  # pragma: no cover - exercised on the CI runner
    # The names stay unbound on purpose: every class that touches them is
    # skipped below, and binding them to None would turn the skipped code into
    # a static "None has no attribute" error.
    HAS_QT = False

requires_qt = unittest.skipUnless(HAS_QT, "PySide6 is not installed")

from dxvk_toolkit import steam  # noqa: E402


def _game(folder: Path, name: str) -> steam.Game:
    return steam.game_from_folder(folder, name)


@requires_qt
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


@requires_qt
class ConfigListModelDocTests(unittest.TestCase):
    """T21: the doc role carries the sectioned documentation for the ⓘ card."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QGuiApplication.instance() or QGuiApplication(["tests"])

    def test_doc_role_carries_three_parts(self) -> None:
        from dxvk_toolkit import confspec
        from dxvk_toolkit.ui.models import ConfigListModel

        model = ConfigListModel()
        model.set_groups(confspec.load_model().groups)
        docs = [row["doc"] for row in model._all if row.get("kind") == "option"]
        self.assertTrue(docs)
        for doc in docs:
            self.assertIsInstance(doc, dict)
            for field in ("summary", "example", "original"):
                self.assertIn(field, doc)
        # Every option documents itself: the example is a key line (the
        # qualifier follows the section - dxvk./dxgi./d3d9.) and the raw
        # upstream block is always available.
        for doc in docs:
            self.assertIn("=", doc["example"])
            self.assertTrue(doc["original"])
        # Curated Chinese summaries exist for at least the common keys.
        self.assertTrue(any(doc["summary"] for doc in docs))

    def test_doc_role_reachable_through_data(self) -> None:
        from dxvk_toolkit import confspec
        from dxvk_toolkit.ui.models import ConfigListModel

        model = ConfigListModel()
        model.set_groups(confspec.load_model().groups)
        position = next(
            i for i, row in enumerate(model._rows) if row.get("kind") == "option"
        )
        doc = model.data(model.index(position, 0), ConfigListModel.DocRole)
        self.assertIsInstance(doc, dict)
        self.assertIn("original", doc)
        # Header rows carry no doc.
        header = next(
            i for i, row in enumerate(model._rows) if row.get("kind") == "header"
        )
        self.assertIsNone(model.data(model.index(header, 0), ConfigListModel.DocRole))


@requires_qt
class GameListModelPlatformI18nTests(unittest.TestCase):
    """T23: platform labels follow the UI language, raw keys stay raw.

    "platformLabel" is what cards, list rows and filter chips display, so it
    goes through _tr(). "platform" keeps the source key (steam, mihoyo, …)
    because filtering and the QML platform colors match on it — 米哈游 used
    to leak into the English UI and never matched the color table either.
    """

    def setUp(self) -> None:
        self._app = QGuiApplication.instance() or QGuiApplication(["tests"])
        self._translator = QTranslator(self._app)
        qm = Path(__file__).resolve().parent.parent / "assets" / "i18n" / "app_en.qm"
        self.assertTrue(qm.is_file(), f"missing catalogue {qm} - run the i18n pipeline")
        self.assertTrue(self._translator.load(str(qm)), f"cannot load {qm}")
        self._app.installTranslator(self._translator)

        from dxvk_toolkit.paths import settings

        settings.set("games_sort", "name:asc", save=False)
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.model = GameListModel()
        self.model.set_games([
            steam.game_from_folder(base / "manual", "Manual Game"),
            steam.Game(appid="12345", name="Genshin", install_dir=base / "genshin",
                       source="mihoyo"),
        ])

    def tearDown(self) -> None:
        self._app.removeTranslator(self._translator)
        self.tmp.cleanup()

    def test_platform_label_is_translated(self) -> None:
        labels = {row["name"]: row["platformLabel"] for row in self.model._all_rows}
        self.assertEqual(labels["Manual Game"], "Manual")
        self.assertEqual(labels["Genshin"], "miHoYo")

    def test_raw_platform_key_is_kept(self) -> None:
        keys = {row["name"]: row["platform"] for row in self.model._all_rows}
        self.assertEqual(keys["Manual Game"], "manual")
        self.assertEqual(keys["Genshin"], "mihoyo")

    def test_filter_chips_are_translated(self) -> None:
        options = {opt["value"]: opt["label"] for opt in self.model.platform_options()}
        self.assertEqual(options[""], "All")
        self.assertEqual(options["manual"], "Manual")
        self.assertEqual(options["mihoyo"], "miHoYo")

    def test_filtering_still_matches_the_raw_key(self) -> None:
        self.model.apply_filter("", "mihoyo", "all")
        self.assertEqual([row["name"] for row in self.model._rows], ["Genshin"])


@requires_qt
class GameListModelRetranslateTests(unittest.TestCase):
    """T25: ui_lang hot-swap rebuilds Python-resolved model strings (§28).

    The model is built in the source language (no catalogue installed yet),
    then the interface language is changed at runtime and retranslate() must
    rebuild the cached platform label and status badge.
    """

    def setUp(self) -> None:
        self._app = QGuiApplication.instance() or QGuiApplication(["tests"])
        # Loaded but NOT installed yet: set_games runs in the source language.
        self._translator = QTranslator(self._app)
        qm = Path(__file__).resolve().parent.parent / "assets" / "i18n" / "app_en.qm"
        self.assertTrue(self._translator.load(str(qm)), f"cannot load {qm}")
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.model = GameListModel()
        self.model.set_games([
            steam.Game(appid="12345", name="Genshin", install_dir=base / "genshin",
                       source="mihoyo"),
        ])

    def tearDown(self) -> None:
        self._app.removeTranslator(self._translator)
        self.tmp.cleanup()

    def test_labels_start_in_source_language(self) -> None:
        row = self.model._all_rows[0]
        self.assertEqual(row["platformLabel"], "米哈游")
        self.assertEqual(row["statusText"], "")

    def test_retranslate_after_installing_translator(self) -> None:
        self._app.installTranslator(self._translator)
        self.model.retranslate()
        row = self.model._all_rows[0]
        self.assertEqual(row["platformLabel"], "miHoYo")
        # A non-existent folder shows the "目录缺失" badge, now in English.
        self.assertEqual(row["statusText"], "Folder missing")
        # The source label is preserved so a later switch back works.
        self.assertEqual(row["platformLabelSrc"], "米哈游")

    def test_retranslate_toggles_both_ways(self) -> None:
        self._app.installTranslator(self._translator)
        self.model.retranslate()
        self.assertEqual(self.model._all_rows[0]["platformLabel"], "miHoYo")
        self._app.removeTranslator(self._translator)
        self.model.retranslate()
        self.assertEqual(self.model._all_rows[0]["platformLabel"], "米哈游")


@requires_qt
class BridgeRefreshTests(unittest.TestCase):
    """The single-row refresh after install/restore must reach the model.

    ``_refresh_one`` used to hand ``_apply_statuses`` a five-field badge tuple,
    which the ``(key, status)`` unpacking rejected silently, so every card kept
    its pre-install state until the next full scan.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QGuiApplication.instance() or QGuiApplication(["tests"])

    @staticmethod
    def _status_text(bridge: object, key: str) -> str:
        row = bridge.model.row(key)  # type: ignore[attr-defined]
        return "" if row is None else str(row.get("statusText") or "")

    def test_refresh_reaches_the_row(self) -> None:
        from dxvk_toolkit.ui.bridge import Bridge

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "refresh"
            folder.mkdir()
            game = steam.game_from_folder(folder, "Refresh")
            bridge = Bridge()
            try:
                bridge._games = {game.key: game}
                bridge.model.set_games([game])
                self.assertEqual(self._status_text(bridge, game.key), "")
                bridge._refresh_one(game)
                deadline = time.time() + 5
                while time.time() < deadline:
                    self._app.processEvents()
                    if self._status_text(bridge, game.key):
                        break
                    time.sleep(0.02)
                self.assertEqual(self._status_text(bridge, game.key), "未安装")
            finally:
                bridge.shutdown()


@requires_qt
class BridgeSchedulingTests(unittest.TestCase):
    """Concurrency bookkeeping the UI depends on."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QGuiApplication.instance() or QGuiApplication(["tests"])

    def test_busy_indicator_stays_until_the_last_task(self) -> None:
        from dxvk_toolkit.ui.bridge import Bridge

        bridge = Bridge()
        try:
            seen: list[bool] = []
            bridge.busyChanged.connect(seen.append)
            bridge._set_busy(True)
            bridge._set_busy(True)
            bridge._set_busy(False)
            self.assertTrue(bridge._busy, "a second task was still running")
            bridge._set_busy(False)
            self.assertFalse(bridge._busy)
            self.assertEqual(seen, [True, False], "one transition per state change")
        finally:
            bridge.shutdown()

    def test_detect_game_is_deduplicated_while_in_flight(self) -> None:
        from dxvk_toolkit.ui.bridge import Bridge

        with tempfile.TemporaryDirectory() as tmp:
            game = steam.game_from_folder(Path(tmp) / "g", "G")
            Path(game.install_dir).mkdir()
            bridge = Bridge()
            try:
                bridge._games = {game.key: game}
                submitted: list[tuple] = []
                bridge._submit = lambda *args, **kwargs: submitted.append(args)  # type: ignore[method-assign]
                bridge.detectGame(game.key)
                bridge.detectGame(game.key)
                self.assertEqual(len(submitted), 1, "the second request must be collapsed")
                self.assertIn(game.key, bridge._detect_pending)
            finally:
                bridge.shutdown()


if __name__ == "__main__":
    unittest.main()
