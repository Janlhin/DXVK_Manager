"""Multi-launcher discovery: Epic manifests, GOG/Ubisoft registry mapping,
and the scan_all_games dedupe pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dxvk_toolkit import steam


class EpicManifestTests(unittest.TestCase):
    def test_valid_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.item").write_text(
                '{"DisplayName": "Fortnite", "InstallLocation": "D:/Games/Fortnite",'
                ' "CatalogItemId": "abc123", "AppName": "FortniteApp",'
                ' "LaunchExecutable": "Fort/Bin/Fort.exe"}',
                encoding="utf-8",
            )
            (root / "b.item").write_text(
                '{"bIsIncomplete": true, "DisplayName": "Broken",'
                ' "InstallLocation": "D:/Broken"}',
                encoding="utf-8",
            )
            (root / "c.item").write_text(
                '{"DisplayName": "NoLocation", "InstallLocation": "  "}',
                encoding="utf-8",
            )
            (root / "d.item").write_text("not json", encoding="utf-8")
            games = steam.scan_epic_games(root)
            self.assertEqual(len(games), 1)
            game = games[0]
            self.assertEqual(game.name, "Fortnite")
            self.assertEqual(game.source, "epic")
            self.assertEqual(game.appid, "abc123")
            self.assertEqual(game.install_dir, Path("D:/Games/Fortnite"))

    def test_appid_fallback_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fallback.item").write_text(
                '{"DisplayName": "OnlyAppName", "InstallLocation": "D:/G",'
                ' "AppName": "gamelocal"}',
                encoding="utf-8",
            )
            games = steam.scan_epic_games(root)
            self.assertEqual(games[0].appid, "gamelocal")


class GogMappingTests(unittest.TestCase):
    def test_paths_and_names(self) -> None:
        entries = [
            ("1207658924", {"path": "D:\\GOG Games\\Hero", "gameName": "Gwent"}),
            ("broken", {"gameName": "No install path"}),
            ("1435828769", {"path": "D:\\GOG Games\\Witcher3"}),
        ]
        games = steam._gog_games_from_entries(entries)
        self.assertEqual([game.name for game in games], ["Gwent", "Witcher3"])
        self.assertTrue(all(game.source == "gog" for game in games))
        self.assertEqual(games[1].appid, "1435828769")


class UbisoftMappingTests(unittest.TestCase):
    def test_dedupe_and_folder_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            entries = [
                ("123", {"InstallDir": str(base / "Valhalla") + "\\"}),
                ("dup", {"InstallDir": str(base / "Valhalla")}),
                ("empty", {"InstallDir": ""}),
            ]
            games = steam._ubisoft_games_from_entries(entries)
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0].name, "Valhalla")
            self.assertEqual(games[0].source, "ubisoft")


class MihoyoMappingTests(unittest.TestCase):
    def test_known_biz_names_and_fallback(self) -> None:
        entries = [
            ("hk4e_cn", {"GameInstallPath": "D:/miHoYo Launcher/Genshin Impact Game"}),
            ("xyz_cn", {"GameInstallPath": "D:/miHoYo Launcher/Unknown Game"}),
            ("nap_cn", {"GameInstallPath": ""}),
        ]
        games = steam._mihoyo_games_from_entries(entries)
        self.assertEqual([game.name for game in games], ["原神", "Unknown Game"])
        self.assertTrue(all(game.source == "mihoyo" for game in games))


class WegameMappingTests(unittest.TestCase):
    def test_game_records_only(self) -> None:
        entries = [
            ("valorant.live", {
                "InstallLocation": "D:\\WeGameApps\\rail_apps\\无畏契约(2001715)\\live",
                "DisplayName": "无畏契约",
                "ManifestId": "7C113126996B9151",
            }),
            ("QQ", {"DisplayName": "QQ"}),
            ("DeskGo", {"InstallLocation": "C:\\Program Files\\DeskGo"}),
        ]
        games = steam._wegame_games_from_entries(entries)
        self.assertEqual(len(games), 1)
        game = games[0]
        self.assertEqual(game.name, "无畏契约")
        self.assertEqual(game.source, "wegame")
        self.assertEqual(game.appid, "7C113126996B9151")


class ScanAllTests(unittest.TestCase):
    def test_dedupes_by_folder_and_sorts_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            steam_game = steam.Game(appid="1", name="Beta", install_dir=root / "b",
                                    source="steam")
            epic_game = steam.Game(appid="2", name="alpha", install_dir=root / "a",
                                   source="epic")
            duplicate = steam.Game(appid="3", name="Beta (other store)",
                                   install_dir=root / "b", source="gog")
            with mock.patch.object(steam, "scan_steam_games",
                                   lambda extra=(): [steam_game]), \
                 mock.patch.object(steam, "scan_epic_games", lambda: [epic_game]), \
                 mock.patch.object(steam, "scan_gog_games", lambda: [duplicate]), \
                 mock.patch.object(steam, "scan_ubisoft_games", lambda: []), \
                 mock.patch.object(steam, "scan_wegame_games", lambda: []), \
                 mock.patch.object(steam, "scan_mihoyo_games", lambda: []):
                games = steam.scan_all_games([])
        self.assertEqual([game.name for game in games], ["alpha", "Beta"])
        self.assertEqual(games[1].source, "steam", "Steam wins the duplicate")

    def test_platform_labels(self) -> None:
        self.assertEqual(steam.PLATFORM_LABELS["epic"], "Epic")
        self.assertEqual(steam.PLATFORM_LABELS["gog"], "GOG")
        self.assertEqual(steam.PLATFORM_LABELS["ubisoft"], "Ubisoft")


class EpicInstallationsTests(unittest.TestCase):
    def test_installations_jsonl_names_games(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game_dir = root / "MyGame"
            game_dir.mkdir()
            # Header line + one installed game + a stale (incomplete, missing
            # on disk) duplicate that must be ignored.
            jsonl = root / "installations.jsonl"
            jsonl.write_text(
                "\n".join([
                    json.dumps({"version": 1, "writtenAt": "x", "entries": 3}),
                    json.dumps({"dir": str(game_dir), "platform": "Windows",
                                "namespace": "ns_real", "complete": True}),
                    json.dumps({"dir": "C:/Ghost/Game", "platform": "Windows",
                                "namespace": "ns_missing", "complete": False}),
                ]),
                encoding="utf-8",
            )
            catalog = root / "cache" / "prod"
            catalog.mkdir(parents=True)
            (catalog / "catalog-cache.json").write_text(
                json.dumps({"items": {
                    "id1": {"item": {"namespace": "ns_real",
                                    "title": "My Cool Game"}},
                }}),
                encoding="utf-8",
            )
            with mock.patch.object(steam, "_egl_data_root", lambda: root):
                games = steam.scan_epic_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].name, "My Cool Game")
        self.assertEqual(games[0].source, "epic")
        self.assertEqual(games[0].install_dir, game_dir)

    def test_fallback_to_folder_name_without_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game_dir = root / "RawFolderName"
            game_dir.mkdir()
            jsonl = root / "installations.jsonl"
            jsonl.write_text(
                json.dumps({"dir": str(game_dir), "namespace": "ns_x",
                            "complete": True}),
                encoding="utf-8",
            )
            with mock.patch.object(steam, "_egl_data_root", lambda: root):
                games = steam.scan_epic_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].name, "RawFolderName")


class WegameRailAppsTests(unittest.TestCase):
    def _make_rail_apps(self, base: Path) -> Path:
        rail = base / "rail_apps"
        rail.mkdir()
        df = rail / "DeltaForce(2001918)"
        df.mkdir()
        (df / "三角洲行动卸载.exe").write_text("", encoding="utf-8")
        val = rail / "无畏契约(2001715)"
        val.mkdir()
        (val / "无畏契约卸载.exe").write_text("", encoding="utf-8")
        return rail

    def test_disk_scan_finds_delta_force_and_valorant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rail = self._make_rail_apps(Path(tmp))
            with mock.patch.object(steam, "_wegame_apps_roots", lambda: [rail]), \
                 mock.patch.object(steam, "_registry_subkey_values",
                                   lambda hive, path: []):
                games = steam.scan_wegame_games()
        self.assertEqual(len(games), 2)
        by_appid = {g.appid: g for g in games}
        self.assertEqual(by_appid["2001918"].name, "三角洲行动")
        self.assertEqual(by_appid["2001918"].install_dir, rail / "DeltaForce(2001918)")
        self.assertEqual(by_appid["2001715"].name, "无畏契约")
        self.assertTrue(all(g.source == "wegame" for g in games))

    def test_display_name_falls_back_to_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rail = Path(tmp) / "rail_apps"
            rail.mkdir()
            plain = rail / "SomeGame(42)"
            plain.mkdir()
            with mock.patch.object(steam, "_wegame_apps_roots", lambda: [rail]), \
                 mock.patch.object(steam, "_registry_subkey_values",
                                   lambda hive, path: []):
                games = steam.scan_wegame_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].name, "SomeGame")
        self.assertEqual(games[0].appid, "42")

    def test_registry_subfolder_deduped_against_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rail = self._make_rail_apps(Path(tmp))
            reg_entries = [
                ("valorant.live", {
                    "InstallLocation": str(rail / "无畏契约(2001715)" / "live"),
                    "DisplayName": "无畏契约",
                    "ManifestId": "7C113126996B9151",
                }),
            ]
            with mock.patch.object(steam, "_wegame_apps_roots", lambda: [rail]), \
                 mock.patch.object(steam, "_registry_subkey_values",
                                   lambda hive, path: reg_entries):
                games = steam.scan_wegame_games()
        self.assertEqual(len(games), 2)
        # the registry live-subfolder record must not add a third/duplicate
        self.assertEqual([g.appid for g in games].count("2001715"), 1)


if __name__ == "__main__":
    unittest.main()
