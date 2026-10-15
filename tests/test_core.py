"""Core self-tests: parser, Steam manifests, installer round trip.

Run with:  python -m unittest discover -s tests -v
Or simply: python tests/test_core.py
"""

from __future__ import annotations

import io
import os
import shutil
import struct
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

# Keep every test away from the real user profile.
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="dxvk-toolkit-tests-"))
os.environ["DXVK_MANAGER_HOME"] = str(_TMP_ROOT)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dxvk_toolkit import confbuild, confspec, installer, sources, steam  # noqa: E402
from dxvk_toolkit.paths import asset_path, ledger  # noqa: E402
from dxvk_toolkit.util import pe_machine  # noqa: E402


def make_fake_pe(path: Path, machine: int) -> None:
    """Write a minimal but structurally valid PE image header."""
    buffer = bytearray(0x200)
    buffer[0:2] = b"MZ"
    struct.pack_into("<I", buffer, 0x3C, 0x80)
    buffer[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", buffer, 0x84, machine)
    path.write_bytes(bytes(buffer))


def make_dxvk_dll(path: Path, text: str = "DXVK: v2.7.1") -> None:
    path.write_bytes(b"\x00" * 128 + text.encode() + b"\x00" * 128)


def make_fake_pe_dll(path: Path, machine: int, text: str = "DXVK: v2.7.1") -> None:
    """A minimal PE carrying a DXVK banner: pe_machine and looks_like_dxvk both bite."""
    buffer = bytearray(0x400)
    buffer[0:2] = b"MZ"
    struct.pack_into("<I", buffer, 0x3C, 0x80)
    buffer[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", buffer, 0x84, machine)
    buffer[0x100 : 0x100 + len(text)] = text.encode()
    path.write_bytes(bytes(buffer))


class ConfSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conf = asset_path("dxvk.conf")
        self.assertTrue(self.conf.is_file(), "bundled reference dxvk.conf is missing")
        self.model = confspec.load_model(self.conf)

    def test_sections_and_keys(self) -> None:
        self.assertGreaterEqual(self.model.option_count, 60)
        for section in ("dxvk", "dxgi", "d3d9", "d3d11"):
            self.assertIn(section, self.model.sections)
        self.assertEqual(self.model.section_order[0], "dxvk")

    def test_types_inferred(self) -> None:
        by_key = {group.key: group for group in self.model.groups}
        self.assertEqual(by_key["hud"].type, "string")
        self.assertEqual(by_key["maxFrameRate"].type, "number")
        self.assertEqual(by_key["enableHDR"].type, "boolean")

    def test_basic_filter_keeps_touched_options(self) -> None:
        basic = self.model.filter(basic_only=True)
        self.assertTrue(basic)
        self.assertTrue(all(g.key in confspec.BASIC_KEYS for g in basic))
        saved = self.model.filter(basic_only=True, current={"deviceFilter": "NVIDIA"})
        self.assertIn("deviceFilter", [g.key for g in saved])

    def test_search(self) -> None:
        found = [group.key for group in self.model.filter("frame rate")]
        self.assertIn("maxFrameRate", found)

    def test_build_conf(self) -> None:
        values = {"hud": "fps,frametimes", "maxFrameRate": "60", "enableHDR": True}
        text = confbuild.build_conf(
            self.model.groups, values, section_order=self.model.section_order
        )
        self.assertIn('dxvk.hud = "fps,frametimes"', text)
        self.assertIn("dxvk.maxFrameRate = 60", text)
        self.assertIn("dxgi.maxFrameRate = 60", text)  # alias written everywhere
        self.assertIn("enableHDR = True", text)  # key exists only in the dxgi section
        self.assertIn("# [dxvk]", text)
        # maxFrameRate exists in dxvk, dxgi and d3d9: every line must be written.
        self.assertIn("d3d9.maxFrameRate = 60", text)
        self.assertNotIn("d3d9.samplerAnisotropy", text)  # untouched options stay out

    def test_quoting_escapes(self) -> None:
        text = confbuild.build_conf(
            self.model.groups,
            {"hud": 'say "hi"'},
            section_order=self.model.section_order,
        )
        self.assertIn(r'dxvk.hud = "say \"hi\""', text)

    def test_boolean_false_is_omitted(self) -> None:
        text = confbuild.build_conf(
            self.model.groups, {"enableHDR": False}, section_order=self.model.section_order
        )
        self.assertNotIn("enableHDR", text)

    def test_bare_reference_values_stay_bare(self) -> None:
        # The reference writes some string options unquoted (Auto, 12_1); the
        # generated file should look the same, but values with spaces must be
        # quoted because DXVK stops at the first unquoted space.
        text = confbuild.build_conf(
            self.model.groups,
            {"maxFeatureLevel": "12_1", "latencySleep": "Auto", "deviceFilter": "0x10DE:0x1B81"},
            section_order=self.model.section_order,
        )
        self.assertIn("d3d11.maxFeatureLevel = 12_1", text)
        self.assertIn("dxvk.latencySleep = Auto", text)
        self.assertIn('dxvk.deviceFilter = "0x10DE:0x1B81"', text)

    def test_bare_value_with_space_is_quoted(self) -> None:
        text = confbuild.build_conf(
            self.model.groups, {"latencySleep": "Low latency"}, section_order=self.model.section_order
        )
        self.assertIn('dxvk.latencySleep = "Low latency"', text)

    def test_import_round_trip(self) -> None:
        values = {
            "hud": "fps,frametimes",
            "maxFrameRate": "60",
            "maxFeatureLevel": "12_1",
            "enableHDR": True,
        }
        text = confbuild.build_conf(
            self.model.groups, values, section_order=self.model.section_order
        )
        parsed, unknown = confspec.parse_config_values(text, self.model)
        self.assertEqual(parsed.get("hud"), "fps,frametimes")
        self.assertEqual(parsed.get("maxFrameRate"), "60")
        self.assertEqual(parsed.get("maxFeatureLevel"), "12_1")
        self.assertIs(parsed.get("enableHDR"), True)
        self.assertEqual(unknown, [])

    def test_import_skips_comments_headers_and_unknowns(self) -> None:
        text = (
            "# [dxvk]\n"
            '# dxvk.hud = "fps"\n'
            "[dxvk]\n"
            'dxvk.hud = "frametimes"\n'
            "dxvk.maxFrameRate = 60\n"
            "not.ours = 1\n"
            "; comment\n"
            "garbage line\n"
        )
        parsed, unknown = confspec.parse_config_values(text, self.model)
        self.assertEqual(parsed.get("hud"), "frametimes")
        self.assertEqual(parsed.get("maxFrameRate"), "60")
        self.assertNotIn("hud_unused", parsed)
        self.assertIn("not.ours", unknown)

    def test_import_ignores_false_booleans(self) -> None:
        parsed, _unknown = confspec.parse_config_values(
            "dxgi.enableHDR = False\n", self.model
        )
        self.assertNotIn("enableHDR", parsed)

    def test_parser_handles_commented_keys(self) -> None:
        model = confspec.build_model(
            "# Some option\n# more docs\n# dxvk.hud = \"fps\"\n\nd3d9.maxFrameRate = 0\n"
        )
        # build_model appends the GPLAsync-only options to every model, so the
        # count has to ignore them.
        own = [g for g in model.groups if g.key not in confspec.GPLASYNC_ONLY]
        self.assertEqual(len(own), 2)
        hud = own[0]
        self.assertEqual(hud.key, "hud")
        self.assertEqual(hud.type, "string")
        self.assertIn("more docs", hud.description())
        self.assertEqual(own[1].type, "number")

    def test_alias_consolidation(self) -> None:
        model = confspec.build_model("[dxvk]\ndxvk.syncInterval = 1\n[dxgi]\ndxgi.syncInterval = 1\n")
        own = [g for g in model.groups if g.key not in confspec.GPLASYNC_ONLY]
        self.assertEqual(len(own), 1)
        self.assertEqual(len(own[0].members), 2)


class SteamTests(unittest.TestCase):
    def test_keyvalues_parser(self) -> None:
        text = '"AppState"\n{\n\t"appid"\t\t"377000"\n\t"name"\t\t"Test Game"\n\t"installdir"\t\t"TestGame"\n\t"StateFlags"\t\t"4"\n}\n'
        data = steam.parse_keyvalues(text)
        self.assertEqual(data["AppState"]["appid"], "377000")
        self.assertEqual(data["AppState"]["StateFlags"], "4")

    def test_scan_library(self) -> None:
        # Isolate from the machine's real Steam installation.
        original_root = steam.steam_root
        steam.steam_root = lambda: None  # type: ignore[assignment]
        try:
            self._scan_library_fixture()
        finally:
            steam.steam_root = original_root  # type: ignore[assignment]

    def _scan_library_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            steamapps = library / "steamapps"
            (steamapps / "common" / "TestGame").mkdir(parents=True)
            (steamapps / "appmanifest_377000.acf").write_text(
                '"AppState"\n{\n"appid"\t\t"377000"\n"name"\t\t"Test Game"\n'
                '"installdir"\t\t"TestGame"\n"StateFlags"\t\t"4"\n"SizeOnDisk"\t\t"1234"\n}\n',
                encoding="utf-8",
            )
            games = steam.scan_steam_games([str(library)])
            self.assertEqual(len(games), 1)
            game = games[0]
            self.assertEqual(game.appid, "377000")
            self.assertEqual(game.name, "Test Game")
            self.assertTrue(game.install_dir.is_dir())
            self.assertTrue(game.is_fully_installed)

    def test_direct3d_guess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "d3d11.dll").write_bytes(b"x")
            (root / "dxgi.dll").write_bytes(b"x")
            self.assertEqual(steam.guess_direct3d(root), "Direct3D 11")

    def test_direct3d_guess_in_bin_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            make_fake_pe(bin_dir / "game.exe", 0x8664)
            with (bin_dir / "game.exe").open("ab") as handle:
                handle.write(b"\x00" * 0x2000)
            (bin_dir / "d3d11.dll").write_bytes(b"x")
            (bin_dir / "dxgi.dll").write_bytes(b"x")
            self.assertTrue(steam.scan_runtime_dlls(root)["d3d11.dll"])
            self.assertEqual(steam.guess_direct3d(root), "Direct3D 11")

    def test_detect_arch_follows_main_exe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            make_fake_pe(root / "EAC.exe", 0x014C)  # 32-bit helper in the root
            exe = bin_dir / "game.exe"
            make_fake_pe(exe, 0x8664)
            with exe.open("ab") as handle:
                handle.write(b"\x00" * 0x2000)  # the real binary is the big one
            self.assertEqual(steam.detect_arch(root), "x64")

    def test_describe_game_sees_bin_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            exe = bin_dir / "game.exe"
            make_fake_pe(exe, 0x8664)
            with exe.open("ab") as handle:
                handle.write(b"\x00" * 0x2000)
            (bin_dir / "d3d11.dll").write_bytes(b"x")
            (bin_dir / "dxgi.dll").write_bytes(b"x")
            info = steam.describe_game(root, persist=False)
            self.assertEqual(info["direct3d"], "Direct3D 11")
            self.assertEqual(info["arch"], "x64")

    def test_folder_stamp_tracks_dll_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            make_fake_pe(bin_dir / "game.exe", 0x8664)
            (bin_dir / "d3d11.dll").write_bytes(b"x")
            stamp_before = steam._folder_stamp(root)
            # Touching the bin directory (DLLs landed or were removed there)
            # must invalidate the stamp - the root mtime alone never changes.
            os.utime(bin_dir, (1_500_000_000, 1_500_000_000))
            self.assertNotEqual(stamp_before, steam._folder_stamp(root))


class ResolveDllDirTests(unittest.TestCase):
    """DXVK lives next to the main executable, which is not always the root."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.game = Path(self.tmp.name) / "game"
        self.game.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_root_exe_stays_root(self) -> None:
        make_fake_pe(self.game / "game.exe", 0x8664)
        self.assertEqual(installer.dll_dir_for(self.game), self.game)

    def test_bin_exe_wins_over_root_stub(self) -> None:
        make_fake_pe(self.game / "SplashScreen.exe", 0x8664)
        exe = self.game / "bin" / "WatchDogs2.exe"
        exe.parent.mkdir()
        make_fake_pe(exe, 0x8664)
        with exe.open("ab") as handle:
            handle.write(b"\x00" * 0x2000)  # the real binary is the big one
        self.assertEqual(installer.dll_dir_for(self.game), self.game / "bin")

    def test_root_dxvk_pins_root(self) -> None:
        bin_dir = self.game / "bin"
        bin_dir.mkdir()
        make_fake_pe(bin_dir / "big.exe", 0x8664)
        with (bin_dir / "big.exe").open("ab") as handle:
            handle.write(b"\x00" * 0x2000)
        make_dxvk_dll(self.game / "d3d11.dll")  # existing root-level install
        self.assertEqual(installer.dll_dir_for(self.game), self.game)

    def test_nothing_at_all_falls_back_to_root(self) -> None:
        self.assertEqual(installer.dll_dir_for(self.game), self.game)
        self.assertEqual(
            installer.dll_dir_for(self.game / "missing"), self.game / "missing"
        )


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.game = base / "game"
        self.game.mkdir()
        self.cache = base / "cache"
        (self.cache / "v2.7.1").mkdir(parents=True)
        for arch in ("x32", "x64"):
            folder = self.cache / "v2.7.1" / arch
            folder.mkdir()
            for dll in ("d3d9.dll", "d3d11.dll", "dxgi.dll"):
                make_dxvk_dll(folder / dll, f"DXVK {arch}")
        # Point the cache at our fixture.
        os.environ["DXVK_MANAGER_HOME"] = str(base / "home")
        self._real_cache = sources.cache_dir
        sources.cache_dir = lambda kind="dxvk": self.cache  # type: ignore[assignment]

    def tearDown(self) -> None:
        sources.cache_dir = self._real_cache  # type: ignore[assignment]
        os.environ["DXVK_MANAGER_HOME"] = str(_TMP_ROOT)
        self.tmp.cleanup()

    def test_dll_plan(self) -> None:
        self.assertEqual(installer.dlls_for_direct3d("Direct3D 9").required, ["d3d9.dll"])
        self.assertEqual(
            installer.dlls_for_direct3d("Direct3D 10").required,
            ["dxgi.dll", "d3d11.dll", "d3d10core.dll"],
        )
        self.assertIn("d3d11.dll", installer.dlls_for_direct3d("Unknown").required)

    def test_arch_from_pe(self) -> None:
        exe = self.game / "game.exe"
        make_fake_pe(exe, 0x014C)
        self.assertEqual(pe_machine(exe), "x32")
        self.assertEqual(installer.choose_arch(self.game), "x32")
        make_fake_pe(exe, 0x8664)
        self.assertEqual(installer.choose_arch(self.game), "x64")

    def test_choose_arch_ignores_root_stub(self) -> None:
        # Watch_Dogs2 shape: a 32-bit anti-cheat helper sits in the root while
        # the real (bigger, 64-bit) executable lives in bin/. The old
        # depth-first pick answered x32 and shipped a game-killing install.
        bin_dir = self.game / "bin"
        bin_dir.mkdir()
        make_fake_pe(self.game / "EAC.exe", 0x014C)
        exe = bin_dir / "game.exe"
        make_fake_pe(exe, 0x8664)
        with exe.open("ab") as handle:
            handle.write(b"\x00" * 0x2000)
        self.assertEqual(installer.choose_arch(self.game), "x64")

    def test_install_arch_mismatch_rolls_back(self) -> None:
        # Corrupt the cached x64 set so the files are actually 32-bit: the
        # post-copy self-check must undo the whole thing.
        bin_dir = self.game / "bin"
        bin_dir.mkdir()
        make_fake_pe(bin_dir / "game.exe", 0x8664)
        for dll in ("d3d11.dll", "dxgi.dll"):
            make_fake_pe_dll(self.cache / "v2.7.1" / "x64" / dll, 0x014C)

        result = installer.install(self.game, "dxvk", "v2.7.1", d3d_hint="Direct3D 11")
        self.assertFalse(result.success)
        self.assertIn("Architecture mismatch", result.message)
        self.assertFalse((bin_dir / "d3d11.dll").exists())
        self.assertFalse((bin_dir / "dxgi.dll").exists())
        self.assertFalse((bin_dir / "d3d11.dll.bkp").exists())
        self.assertFalse(ledger.get(self.game))

    def test_remove_artifacts(self) -> None:
        make_fake_pe(self.game / "game.exe", 0x8664)
        make_dxvk_dll(self.game / "d3d11.dll")
        (self.game / "dxvk.conf").write_text("dxvk.hud = fps\n", encoding="utf-8")
        (self.game / "game.exe_dxgi.log").write_text("info:", encoding="utf-8")
        (self.game / "game.exe.dxvk-cache").write_bytes(b"\x00" * 8)
        (self.game / "unrelated.log").write_text("keep me", encoding="utf-8")

        removed = installer.remove_artifacts(self.game)
        self.assertIn("dxvk.conf", removed)
        self.assertIn("game.exe_dxgi.log", removed)
        self.assertIn("game.exe.dxvk-cache", removed)
        self.assertNotIn("unrelated.log", removed)
        self.assertTrue((self.game / "unrelated.log").is_file())
        self.assertTrue((self.game / "d3d11.dll").is_file())  # DLLs are not artifacts

    def test_remove_dxvk_with_artifacts(self) -> None:
        make_fake_pe(self.game / "game.exe", 0x8664)
        (self.game / "d3d11.dll").write_bytes(b"original")
        result = installer.install(self.game, "dxvk", "v2.7.1", d3d_hint="Direct3D 11")
        self.assertTrue(result.success, result.message)
        installer.write_conf(self.game, 'dxvk.hud = "fps"\n')
        (self.game / "game.exe_d3d11.log").write_text("info:", encoding="utf-8")

        removed = installer.remove_dxvk(self.game, artifacts=True)
        self.assertIn("d3d11.dll", removed)
        self.assertIn("dxgi.dll", removed)
        self.assertIn("dxvk.conf", removed)
        self.assertIn("game.exe_d3d11.log", removed)
        self.assertFalse((self.game / "d3d11.dll").exists())
        # The originals stay restorable; only DXVK's own traces go.
        self.assertTrue((self.game / "d3d11.dll.bkp").is_file())

    def test_prune_missing(self) -> None:
        gone = Path(self.tmp.name) / "uninstalled-game"
        ledger.record(gone, patched=True, dxvk_version="v1.0")
        ledger.record(self.game, patched=True, dxvk_version="v2.7.1")

        dropped = ledger.prune_missing()
        self.assertTrue(any("uninstalled-game" in path for path in dropped))
        self.assertFalse(ledger.get(gone))
        self.assertTrue(ledger.get(self.game))  # live folders survive

    def test_cache_stats_and_clear(self) -> None:
        # Own cache dir: clearing must not disturb the shared fixture for the
        # other tests in this class.
        own = Path(self.tmp.name) / "own-cache"
        (own / "v2.7.1" / "x64").mkdir(parents=True)
        (own / "v2.7.1" / "x32").mkdir(parents=True)
        (own / "v0.9").mkdir()
        for dll in ("d3d11.dll", "dxgi.dll"):
            make_dxvk_dll(own / "v2.7.1" / "x64" / dll)
            make_dxvk_dll(own / "v2.7.1" / "x32" / dll)
        real = sources.cache_dir
        sources.cache_dir = lambda kind="dxvk": own  # type: ignore[assignment]

        ledger.record(self.game, patched=True, dxvk_version="v2.7.1", dxvk_type="dxvk")
        stats = sources.cache_stats("dxvk")
        by_name = {entry["version"]: entry for entry in stats["versions"]}
        self.assertTrue(by_name["v2.7.1"]["used"])
        self.assertFalse(by_name["v2.7.1"]["broken"])
        self.assertTrue(by_name["v0.9"]["broken"])  # no x32/x64 layout

        removed = sources.clear_cache("dxvk", keep_used=True)
        self.assertIn("v0.9", removed)
        self.assertNotIn("v2.7.1", removed)
        self.assertTrue((own / "v2.7.1").is_dir())

        removed = sources.clear_cache("dxvk", keep_used=False)
        self.assertIn("v2.7.1", removed)
        self.assertFalse((own / "v2.7.1").is_dir())
        sources.cache_dir = real  # type: ignore[assignment]

    def test_install_inspect_restore(self) -> None:
        make_fake_pe(self.game / "game.exe", 0x8664)
        (self.game / "d3d11.dll").write_bytes(b"original-d3d11")
        (self.game / "dxgi.dll").write_bytes(b"original-dxgi")

        result = installer.install(self.game, "dxvk", "v2.7.1", d3d_hint="Direct3D 11")
        self.assertTrue(result.success, result.message)
        self.assertEqual(sorted(result.copied), ["d3d11.dll", "dxgi.dll"])
        self.assertTrue((self.game / "d3d11.dll.bkp").is_file())
        self.assertIn(b"DXVK", (self.game / "d3d11.dll").read_bytes())

        status = installer.inspect(self.game)
        self.assertTrue(status.patched)
        self.assertTrue(status.backuped)
        self.assertEqual(status.version, "v2.7.1")
        self.assertEqual(sorted(status.dxvk_files), ["d3d11.dll", "dxgi.dll"])

        restored = installer.restore(self.game)
        self.assertTrue(restored.success, restored.message)
        self.assertEqual(sorted(restored.restored), ["d3d11.dll", "dxgi.dll"])
        self.assertEqual((self.game / "d3d11.dll").read_bytes(), b"original-d3d11")
        self.assertFalse((self.game / "d3d11.dll.bkp").exists())

    def test_write_conf(self) -> None:
        path = installer.write_conf(self.game, "dxvk.hud = \"fps\"\n")
        self.assertTrue(path.is_file())
        self.assertIn("fps", installer.read_conf(self.game))
        self.assertTrue(installer.inspect(self.game).conf_present)

    def test_install_into_bin_layout(self) -> None:
        bin_dir = self.game / "bin"
        bin_dir.mkdir()
        make_fake_pe(bin_dir / "game.exe", 0x8664)
        (bin_dir / "d3d11.dll").write_bytes(b"original-d3d11")
        (bin_dir / "dxgi.dll").write_bytes(b"original-dxgi")

        result = installer.install(self.game, "dxvk", "v2.7.1", d3d_hint="Direct3D 11")
        self.assertTrue(result.success, result.message)
        self.assertEqual(sorted(result.copied), ["d3d11.dll", "dxgi.dll"])
        self.assertTrue((bin_dir / "d3d11.dll.bkp").is_file())
        self.assertIn(b"DXVK", (bin_dir / "d3d11.dll").read_bytes())
        self.assertFalse((self.game / "d3d11.dll").exists())  # root stays clean

        status = installer.inspect(self.game)
        self.assertTrue(status.patched)
        self.assertTrue(status.backuped)
        self.assertEqual(status.version, "v2.7.1")
        self.assertEqual(status.dll_dir, str(bin_dir))
        self.assertEqual(sorted(status.dxvk_files), ["d3d11.dll", "dxgi.dll"])
        self.assertEqual(ledger.get(self.game).get("dll_dir"), "bin")

        conf_path = installer.write_conf(self.game, 'dxvk.hud = "fps"\n')
        self.assertEqual(conf_path.parent, bin_dir)
        self.assertTrue(installer.inspect(self.game).conf_present)

        restored = installer.restore(self.game)
        self.assertTrue(restored.success, restored.message)
        self.assertEqual(sorted(restored.restored), ["d3d11.dll", "dxgi.dll"])
        self.assertEqual((bin_dir / "d3d11.dll").read_bytes(), b"original-d3d11")
        self.assertFalse((bin_dir / "d3d11.dll.bkp").exists())


def _release_tarball() -> Path:
    """A tar.gz shaped like a real DXVK package: one folder, x32 + x64."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for arch in ("x32", "x64"):
            for name in ("d3d11.dll", "dxgi.dll"):
                data = f"{arch}-{name}".encode()
                info = tarfile.TarInfo(f"dxvk-3.1.1/{arch}/{name}")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    path = Path(tempfile.mkdtemp(prefix="dxvk-tarball-")) / "dxvk-3.1.1.tar.gz"
    path.write_bytes(buffer.getvalue())
    return path


class ReleasesCacheTests(unittest.TestCase):
    """T24: a fallback listing must not blank known date/size metadata.

    When GitHub rate limits the API, the listing comes from jsDelivr tags
    (no date, no size) and the detail panel used to show "-" for every
    version, including ones freshly downloaded through the CLI.
    """

    def setUp(self) -> None:
        # The cache merge keeps metadata across writes by design, so each
        # test starts from no cache at all.
        sources._cache_file("dxvk").unlink(missing_ok=True)

    def _release(self, version: str, date: str = "", size: int = 0) -> sources.Release:
        return sources.Release(
            kind="dxvk",
            version=version,
            label=f"DXVK {version}",
            url=(
                f"https://github.com/doitsujin/dxvk/releases/download/"
                f"{version}/dxvk-{version.lstrip('v')}.tar.gz"
            ),
            date=date,
            size=size,
            file_name=f"dxvk-{version.lstrip('v')}.tar.gz",
        )

    def _cached(self) -> dict[str, sources.Release]:
        return {item.version: item for item in sources.cached_releases("dxvk")}

    def test_fallback_write_keeps_known_metadata(self) -> None:
        sources.cache_releases("dxvk", [self._release("v3.1.1", date="2025-06-01", size=12345678)])
        # A rate-limited refresh falls back to jsDelivr: no date, no size.
        sources.cache_releases("dxvk", [self._release("v3.1.1")])
        entry = self._cached()["v3.1.1"]
        self.assertEqual(entry.date, "2025-06-01")
        self.assertEqual(entry.size, 12345678)

    def test_note_download_backfills_size_and_marks_stale(self) -> None:
        sources.cache_releases("dxvk", [self._release("v3.1.1")])
        sources._note_download("dxvk", "v3.1.1", 9988776)
        self.assertEqual(self._cached()["v3.1.1"].size, 9988776)
        # The date is still missing, so the cache counts as stale until a
        # refresh can fill the rest in.
        self.assertGreater(sources.cache_age("dxvk"), 6 * 3600)

    def test_note_download_leaves_a_complete_listing_alone(self) -> None:
        sources.cache_releases("dxvk", [self._release("v3.1.1", date="2025-06-01", size=12345678)])
        sources._note_download("dxvk", "v3.1.1", 9988776)
        entry = self._cached()["v3.1.1"]
        self.assertEqual(entry.size, 12345678)  # the listing already knew
        self.assertLess(sources.cache_age("dxvk"), 60)

    def test_download_release_records_archive_size(self) -> None:
        from dxvk_toolkit import net

        sources.cache_releases("dxvk", [self._release("v3.1.1")])
        tarball = _release_tarball()
        original = net.http_download

        def fake_download(url: str, destination, **kwargs) -> int:
            shutil.copyfile(tarball, destination)
            return tarball.stat().st_size

        net.http_download = fake_download
        try:
            root = sources.download_release(self._release("v3.1.1"))
        finally:
            net.http_download = original
        self.assertTrue((root / "x64").is_dir())
        self.assertEqual(self._cached()["v3.1.1"].size, tarball.stat().st_size)


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(
        [
            loader.loadTestsFromTestCase(ConfSpecTests),
            loader.loadTestsFromTestCase(SteamTests),
            loader.loadTestsFromTestCase(ResolveDllDirTests),
            loader.loadTestsFromTestCase(InstallerTests),
            loader.loadTestsFromTestCase(ReleasesCacheTests),
        ]
    )
    runner = unittest.TextTestRunner(verbosity=2)
    return 0 if runner.run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
