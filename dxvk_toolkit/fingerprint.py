"""Fingerprint DXVK DLLs that were not installed by this tool.

A game folder may already contain DXVK dropped in by hand or by another
manager. This module answers three questions for such an installation:

1. *Is it DXVK at all?* - the VERSIONINFO resource carries
   ``ProductName = "DXVK"`` on every official build.
2. *Which version?* - DXVK masks FileVersion as a Windows system version
   (``10.0.17763.1``), so the real number is read from the version banner
   string embedded next to the log tags inside the binary.
3. *Was it modified?* - SHA-256 the file and compare against every DLL
   inside the local download cache; a hit proves the exact official build,
   a miss means the file differs from everything we know.

The takeover (adopt) operation then records the installation in the ledger
so future installs/updates behave like tool-managed ones, optionally
building restore points from the Windows system directories.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import shutil
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from . import sources
from .installer import BACKUP_SUFFIX, CONF_NAME, invalidate, relative_dll_dir
from .paths import ledger
from .util import log, pe_machine, resolve_dll_dir

# Every DLL the fingerprint looks at (superset of what DXVK actually ships).
DLL_NAMES = ("d3d8.dll", "d3d9.dll", "d3d10core.dll", "d3d11.dll", "d3d12.dll", "dxgi.dll")

# System directories that hold the original Windows copies, per arch.
_SYSTEM_DIRS = {"x64": r"C:\Windows\System32", "x32": r"C:\Windows\SysWOW64"}

# DXVK embeds its banner as an ASCII constant next to the log tags, e.g.
# b"\x00DXVK: \x00v3.1.1\x00". Restrict to plausible version ranges so random
# three-part numbers elsewhere in the binary do not match.
_EMBEDDED_RE = re.compile(rb"\x00v(\d{1,2})\.(\d{1,3})\.(\d{1,4})\x00")


@dataclass
class DllFingerprint:
    """Verdict for one DLL found in a game folder."""

    name: str
    present: bool = False
    is_dxvk: bool = False
    arch: str = ""            # x32 / x64, from the PE header
    size: int = 0
    sha256: str = ""
    product: str = ""         # VERSIONINFO ProductName
    file_description: str = ""
    embedded_version: str = ""  # e.g. "3.1.1" from the banner string
    matched: str = ""         # "<kind> <version> <arch>" when the hash hit the cache

    @property
    def official(self) -> bool:
        return bool(self.matched)


@dataclass
class Fingerprint:
    """Everything known about a possibly-unmanaged DXVK installation."""

    install_dir: str
    dlls: list[DllFingerprint] = field(default_factory=list)
    version: str = ""          # best-effort DXVK version ("3.1.1")
    kind: str = ""             # "dxvk" / "gplasync" when proven by hash
    arch: str = ""
    managed: bool = False      # ledger already has a patched record
    backuped: bool = False     # .bkp files exist
    conf_present: bool = False
    dll_dir: str = ""          # directory the DLLs were found in (exe folder)

    @property
    def dxvk_dlls(self) -> list[DllFingerprint]:
        return [dll for dll in self.dlls if dll.is_dxvk]

    @property
    def official(self) -> bool:
        dxvk = self.dxvk_dlls
        return bool(dxvk) and all(dll.matched for dll in dxvk)

    @property
    def unverifiable(self) -> bool:
        """DXVK files exist but the local cache could not confirm any of them."""
        dxvk = self.dxvk_dlls
        return bool(dxvk) and not any(dll.matched for dll in dxvk)


# --------------------------------------------------------------------------
# VERSIONINFO (Windows only; other platforms simply yield no strings)
# --------------------------------------------------------------------------

def read_version_strings(path: str | os.PathLike[str]) -> dict[str, str]:
    """String table of the file's VERSIONINFO resource ({} when unavailable)."""
    if os.name != "nt":
        return {}
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return {}
        data = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(str(path), 0, size, data):
            return {}
        buf = ctypes.c_void_p()
        blen = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(
            data, "\\VarFileInfo\\Translation", ctypes.byref(buf), ctypes.byref(blen)
        ) or blen.value < 4:
            return {}
        words = ctypes.cast(buf, ctypes.POINTER(ctypes.c_uint16 * 2)).contents
        prefix = f"\\StringFileInfo\\{words[0]:04x}{words[1]:04x}\\"
        out: dict[str, str] = {}
        for key in ("ProductName", "FileDescription", "FileVersion", "ProductVersion"):
            item = ctypes.c_void_p()
            ilen = ctypes.c_uint()
            if ctypes.windll.version.VerQueryValueW(
                data, prefix + key, ctypes.byref(item), ctypes.byref(ilen)
            ) and ilen.value:
                out[key] = ctypes.wstring_at(item, ilen.value - 1)
        return out
    except OSError:  # pragma: no cover - defensive, Windows API edge cases
        return {}


def embedded_version(data: bytes) -> str:
    """Pull the DXVK version out of the binary's banner strings.

    The banner sits deep inside multi-megabyte main DLLs (next to the log
    tags, ~6 MB into d3d11.dll), so the whole file must be scanned.
    """
    for match in _EMBEDDED_RE.finditer(data):
        return f"{match.group(1).decode()}.{match.group(2).decode()}.{match.group(3).decode()}"
    return ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


# --------------------------------------------------------------------------
# Cache hash index
# --------------------------------------------------------------------------

def build_cache_index(kinds: Iterable[str] = ("dxvk", "gplasync")) -> dict[str, tuple[str, str, str]]:
    """Map sha256 -> (kind, version, arch) for every DLL in the local cache."""
    index: dict[str, tuple[str, str, str]] = {}
    for kind in kinds:
        root = sources.cache_dir(kind)
        try:
            versions = [child for child in root.iterdir() if child.is_dir()]
        except OSError:
            continue
        for version_dir in versions:
            bin_root = sources.find_bin_root(version_dir)
            if bin_root is None:
                continue
            for arch in ("x64", "x32"):
                folder = bin_root / arch
                if not folder.is_dir():
                    continue
                try:
                    files = [c for c in folder.iterdir() if c.suffix.lower() == ".dll"]
                except OSError:
                    continue
                for dll in files:
                    digest = _sha256(dll)
                    if digest:
                        index.setdefault(digest, (kind, version_dir.name, arch))
    return index


_INDEX: dict[str, tuple[str, str, str]] | None = None
_INDEX_STAMP: float = 0.0


def _cache_index() -> dict[str, tuple[str, str, str]]:
    """Memoized cache index, rebuilt when the download cache changes size."""
    global _INDEX, _INDEX_STAMP
    stamp = 0.0
    for kind in ("dxvk", "gplasync"):
        try:
            stamp += sum(
                child.stat().st_mtime
                for child in sources.cache_dir(kind).iterdir()
                if child.is_dir()
            )
        except OSError:
            pass
    if _INDEX is None or stamp != _INDEX_STAMP:
        _INDEX = build_cache_index()
        _INDEX_STAMP = stamp
    return _INDEX


def forget_cache_index() -> None:
    """Drop the memoized hash index (call after downloads/deletions)."""
    global _INDEX
    _INDEX = None


# --------------------------------------------------------------------------
# Fingerprinting one game folder
# --------------------------------------------------------------------------

def fingerprint_game(game_dir: str | os.PathLike[str]) -> Fingerprint:
    """Inspect a game folder's DLLs and classify the DXVK installation."""
    root = Path(game_dir)
    result = Fingerprint(install_dir=str(root))
    record = ledger.get(root)
    result.managed = bool(record.get("patched"))
    dll_dir = resolve_dll_dir(root, DLL_NAMES)
    result.dll_dir = str(dll_dir)
    if dll_dir.is_dir():
        result.backuped = any(
            child.name.lower().endswith(BACKUP_SUFFIX)
            for child in dll_dir.iterdir()
            if child.is_file()
        )
    result.conf_present = (dll_dir / CONF_NAME).is_file()

    versions: list[str] = []
    dxvk_found = False
    for name in DLL_NAMES:
        path = dll_dir / name
        dll = DllFingerprint(name=name)
        if not path.is_file():
            result.dlls.append(dll)
            continue
        dll.present = True
        dll.size = path.stat().st_size
        dll.arch = pe_machine(path)
        data = b""
        try:
            with path.open("rb") as handle:
                data = handle.read()
        except OSError:
            pass
        dll.is_dxvk = b"DXVK" in data
        if not dll.is_dxvk:
            result.dlls.append(dll)
            continue
        dxvk_found = True
        strings = read_version_strings(path)
        dll.product = strings.get("ProductName", "")
        dll.file_description = strings.get("FileDescription", "")
        dll.embedded_version = embedded_version(data)
        if dll.embedded_version:
            versions.append(dll.embedded_version)
        result.dlls.append(dll)

    # The hash index scans the whole download cache; only pay for that when
    # there is actually something DXVK-shaped to verify.
    if dxvk_found:
        index = _cache_index()
        for dll in result.dxvk_dlls:
            dll.sha256 = _sha256(dll_dir / dll.name)
            hit = index.get(dll.sha256)
            if hit:
                kind, version, arch = hit
                dll.matched = f"{kind} {version} {arch}"
                if not result.kind:
                    result.kind = kind
                if not result.arch:
                    result.arch = arch

    if versions:
        # The banner is present in the big main DLLs; majority vote across
        # the set guards against a stray constant.
        result.version = max(set(versions), key=versions.count)
    if not result.arch:
        for dll in result.dxvk_dlls:
            if dll.arch in ("x32", "x64"):
                result.arch = dll.arch
                break
    return result


# --------------------------------------------------------------------------
# Takeover
# --------------------------------------------------------------------------

def backup_from_system(
    game_dir: str | os.PathLike[str],
    dll: str,
    arch: str = "x64",
    target_dir: Path | None = None,
) -> Path | None:
    """Build a restore point for one DLL from the Windows system directory.

    The game's own pre-DXVK file is gone once a foreign install overwrote it,
    so the closest thing to the original state is the system copy. The backup
    is clearly derived (not the true original) - the ledger note says so.
    """
    if os.name != "nt":
        return None
    folder = _SYSTEM_DIRS.get(arch, _SYSTEM_DIRS["x64"])
    source = Path(folder) / dll
    if not source.is_file():
        return None
    root = Path(game_dir)
    directory = target_dir if target_dir is not None else root
    target = directory / (dll + BACKUP_SUFFIX)
    if target.exists():
        return target
    try:
        shutil.copy2(source, target)
    except OSError as exc:
        log.warning("system backup failed for %s: %s", dll, exc)
        return None
    return target


def adopt(game_dir: str | os.PathLike[str], *, backup_from_system_dirs: bool = False) -> tuple[str, list[str]]:
    """Take over an existing DXVK installation into this tool's ledger.

    Returns (message, backed_up_dlls). After adoption the game shows its real
    DXVK version in the UI, and installing another version upgrades in place
    without re-backing the DXVK DLLs as if they were originals.
    """
    root = Path(game_dir)
    if not root.is_dir():
        return (f"Game folder not found: {root}", [])

    fp = fingerprint_game(root)
    if not fp.dxvk_dlls:
        return ("No DXVK DLLs were found in this folder - nothing to take over", [])

    dll_dir = Path(fp.dll_dir) if fp.dll_dir else root
    backed: list[str] = []
    if backup_from_system_dirs:
        for dll in fp.dxvk_dlls:
            arch = dll.arch or fp.arch or "x64"
            if backup_from_system(root, dll.name, arch, target_dir=dll_dir):
                backed.append(dll.name)

    names = [dll.name for dll in fp.dxvk_dlls]
    ledger.record(
        root,
        patched=True,
        backuped=bool(fp.backuped or backed),
        dxvk_version=f"v{fp.version}" if fp.version else "",
        dxvk_type=fp.kind or "dxvk",
        adopted=True,
        adopted_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        system_backups=backed,
        arch=fp.arch,
        dlls=names,
        dll_dir=relative_dll_dir(root, dll_dir),
    )
    invalidate(root)
    forget_cache_index()

    label = f"DXVK v{fp.version}" if fp.version else "DXVK (version unknown)"
    if fp.official:
        proven = "; hashes match the official cache"
    elif fp.unverifiable:
        proven = "; differs from the local cache (modified or unofficial build)"
    else:
        proven = ""
    note = f"; {len(backed)} restore point(s) built from the system directories" if backed else ""
    return (f"Adopted {label}{proven}{note}", backed)
