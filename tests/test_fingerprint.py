"""Fingerprinting and takeover of foreign DXVK installations."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from dxvk_toolkit import fingerprint, installer, sources
from dxvk_toolkit.paths import ledger
from tests.test_core import _TMP_ROOT, make_fake_pe

_BANNER = b"\x00DXVK: \x00v3.1.1\x00Build: \x00x86\x00"


def _dxvk_dll(path: Path, version: str = "3.1.1") -> None:
    body = f"\x00DXVK: \x00v{version}\x00Build: \x00x86\x00".encode()
    path.write_bytes(b"\x00" * 64 + body + b"\x00" * 64)


class EmbeddedVersionTests(unittest.TestCase):
    def test_banner_extraction(self) -> None:
        self.assertEqual(fingerprint.embedded_version(_BANNER), "3.1.1")

    def test_banner_after_padding(self) -> None:
        data = b"\x00" * 200 + _BANNER + b"\x00" * 5000
        self.assertEqual(fingerprint.embedded_version(data), "3.1.1")

    def test_absent(self) -> None:
        self.assertEqual(fingerprint.embedded_version(b"MZ" + b"\x00" * 4096), "")

    def test_implausible_numbers_ignored(self) -> None:
        data = b"\x00v99.99.99999\x00" + _BANNER
        self.assertEqual(fingerprint.embedded_version(data), "3.1.1")


class FingerprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.game = base / "game"
        self.game.mkdir()
        make_fake_pe(self.game / "game.exe", 0x8664)
        # Two versions in the cache; the game carries both a verbatim copy
        # of v3.1.1 and a file that matches nothing (a modified build).
        self.cache = base / "cache"
        for version in ("v3.1.1", "v2.7.1"):
            for arch in ("x64", "x32"):
                folder = self.cache / version / arch
                folder.mkdir(parents=True)
                for dll in ("d3d9.dll", "d3d11.dll", "dxgi.dll"):
                    _dxvk_dll(folder / dll, version.lstrip("v"))
        os.environ["DXVK_MANAGER_HOME"] = str(base / "home")
        self._real_cache = sources.cache_dir
        sources.cache_dir = lambda kind="dxvk": self.cache  # type: ignore[assignment]
        fingerprint.forget_cache_index()

    def tearDown(self) -> None:
        sources.cache_dir = self._real_cache  # type: ignore[assignment]
        os.environ["DXVK_MANAGER_HOME"] = str(_TMP_ROOT)
        fingerprint.forget_cache_index()
        self.tmp.cleanup()

    def test_official_install_is_matched(self) -> None:
        _dxvk_dll(self.game / "d3d11.dll", "3.1.1")
        _dxvk_dll(self.game / "dxgi.dll", "3.1.1")
        fp = fingerprint.fingerprint_game(self.game)
        self.assertFalse(fp.managed)
        self.assertTrue(fp.official)
        self.assertEqual(fp.version, "3.1.1")
        self.assertEqual(fp.kind, "dxvk")
        self.assertEqual(fp.arch, "x64")
        for dll in fp.dxvk_dlls:
            self.assertTrue(dll.matched.startswith("dxvk v3.1.1"), dll.matched)

    def test_modified_build_is_unverifiable(self) -> None:
        _dxvk_dll(self.game / "d3d11.dll", "3.1.1")
        # Overwrite with a mutated build: same banner, different bytes.
        path = self.game / "d3d11.dll"
        path.write_bytes(path.read_bytes() + b"\x01\x02\x03")
        _dxvk_dll(self.game / "dxgi.dll", "3.1.1")
        (self.game / "dxgi.dll").write_bytes((self.game / "dxgi.dll").read_bytes() + b"\x04\x05")
        fp = fingerprint.fingerprint_game(self.game)
        self.assertFalse(fp.official)
        self.assertTrue(fp.unverifiable)
        self.assertEqual(fp.version, "3.1.1")  # banner still readable

    def test_non_dxvk_folder_is_quiet(self) -> None:
        (self.game / "d3d11.dll").write_bytes(b"original-d3d11")
        fp = fingerprint.fingerprint_game(self.game)
        self.assertFalse(fp.dxvk_dlls)
        self.assertFalse(fp.official)

    def test_conf_and_backups_reported(self) -> None:
        _dxvk_dll(self.game / "d3d11.dll", "3.1.1")
        (self.game / "d3d11.dll.bkp").write_bytes(b"original")
        (self.game / "dxvk.conf").write_text("dxvk.hud = fps\n", encoding="utf-8")
        fp = fingerprint.fingerprint_game(self.game)
        self.assertTrue(fp.backuped)
        self.assertTrue(fp.conf_present)

    def test_bin_layout_is_fingerprinted(self) -> None:
        # Watch_Dogs2 style: the exe (and any DXVK) live in a subdirectory.
        # Drop the setUp exe so its name cannot match the folder ("game").
        (self.game / "game.exe").unlink()
        make_fake_pe(self.game / "SplashScreen.exe", 0x8664)
        bin_dir = self.game / "bin"
        bin_dir.mkdir()
        make_fake_pe(bin_dir / "WatchDogs2.exe", 0x8664)
        with (bin_dir / "WatchDogs2.exe").open("ab") as handle:
            handle.write(b"\x00" * 0x2000)  # bigger than the root stub
        _dxvk_dll(bin_dir / "d3d11.dll", "3.1.1")
        _dxvk_dll(bin_dir / "dxgi.dll", "3.1.1")
        fp = fingerprint.fingerprint_game(self.game)
        self.assertEqual(fp.dll_dir, str(bin_dir))
        self.assertTrue(fp.official)
        self.assertEqual(fp.version, "3.1.1")
        self.assertEqual(fp.arch, "x64")


class AdoptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.game = base / "game"
        self.game.mkdir()
        make_fake_pe(self.game / "game.exe", 0x8664)
        self.cache = base / "cache"
        folder = self.cache / "v2.7.1" / "x64"
        folder.mkdir(parents=True)
        folder32 = self.cache / "v2.7.1" / "x32"
        folder32.mkdir(parents=True)
        for dll in ("d3d9.dll", "d3d11.dll", "dxgi.dll"):
            _dxvk_dll(folder / dll, "2.7.1")
            _dxvk_dll(folder32 / dll, "2.7.1")
        os.environ["DXVK_MANAGER_HOME"] = str(base / "home")
        self._real_cache = sources.cache_dir
        sources.cache_dir = lambda kind="dxvk": self.cache  # type: ignore[assignment]
        fingerprint.forget_cache_index()

    def tearDown(self) -> None:
        sources.cache_dir = self._real_cache  # type: ignore[assignment]
        os.environ["DXVK_MANAGER_HOME"] = str(_TMP_ROOT)
        fingerprint.forget_cache_index()
        self.tmp.cleanup()

    def test_adopt_records_ledger_and_unlocks_upgrade(self) -> None:
        _dxvk_dll(self.game / "d3d11.dll", "3.1.1")
        _dxvk_dll(self.game / "dxgi.dll", "3.1.1")

        # A foreign install blocks a blind install (it would archive the DXVK
        # DLLs as "originals").
        blocked = installer.install(self.game, "dxvk", "v2.7.1", d3d_hint="Direct3D 11")
        self.assertFalse(blocked.success)
        self.assertIn("Adopt", blocked.message)

        message, backed = fingerprint.adopt(self.game)
        self.assertEqual(backed, [])
        record = ledger.get(self.game)
        self.assertTrue(record.get("adopted"))
        self.assertEqual(record.get("dxvk_version"), "v3.1.1")
        self.assertFalse(record.get("backuped"))

        status = installer.inspect(self.game)
        self.assertTrue(status.patched)
        self.assertEqual(status.version, "v3.1.1")

        # After adoption the upgrade goes through without bogus backups.
        result = installer.install(self.game, "dxvk", "v2.7.1", d3d_hint="Direct3D 11")
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.backed_up, [])
        self.assertEqual((self.game / "d3d11.dll").read_bytes().count(b"v2.7.1"), 1)
        record = ledger.get(self.game)
        self.assertEqual(record.get("dxvk_version"), "v2.7.1")

    def test_adopt_requires_dxvk(self) -> None:
        (self.game / "d3d11.dll").write_bytes(b"original")
        message, backed = fingerprint.adopt(self.game)
        self.assertFalse(backed)
        self.assertIn("No DXVK", message)

    def test_adopt_and_upgrade_bin_layout(self) -> None:
        bin_dir = self.game / "bin"
        bin_dir.mkdir()
        make_fake_pe(self.game / "SplashScreen.exe", 0x8664)
        make_fake_pe(bin_dir / "game.exe", 0x8664)
        with (bin_dir / "game.exe").open("ab") as handle:
            handle.write(b"\x00" * 0x2000)
        _dxvk_dll(bin_dir / "d3d11.dll", "3.1.1")
        _dxvk_dll(bin_dir / "dxgi.dll", "3.1.1")

        message, backed = fingerprint.adopt(self.game)
        self.assertIn("Adopted DXVK v3.1.1", message)
        self.assertFalse(backed)
        self.assertEqual(ledger.get(self.game).get("dll_dir"), "bin")

        upgrade = installer.install(self.game, "dxvk", "v2.7.1", d3d_hint="Direct3D 11")
        self.assertTrue(upgrade.success, upgrade.message)
        self.assertIn(b"v2.7.1", (bin_dir / "d3d11.dll").read_bytes())
        self.assertFalse((self.game / "d3d11.dll").exists())  # root stays clean

    @unittest.skipUnless(os.name == "nt", "system backup needs Windows")
    def test_backup_from_system(self) -> None:
        _dxvk_dll(self.game / "d3d9.dll", "3.1.1")
        built = fingerprint.backup_from_system(self.game, "d3d9.dll", "x64")
        self.assertIsNotNone(built)
        self.assertTrue((self.game / "d3d9.dll.bkp").is_file())
        self.assertGreater((self.game / "d3d9.dll.bkp").stat().st_size, 0)
        # A second call does not clobber the first backup.
        again = fingerprint.backup_from_system(self.game, "d3d9.dll", "x64")
        self.assertEqual(again, built)


if __name__ == "__main__":
    unittest.main()
