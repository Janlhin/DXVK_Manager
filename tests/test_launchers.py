"""Multi-launcher discovery: Epic manifests, GOG/Ubisoft registry mapping,
and the scan_all_games dedupe pipeline."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
