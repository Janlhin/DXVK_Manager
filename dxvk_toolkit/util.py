"""Small helpers shared by the CLI-worthy core and the GUI."""

from __future__ import annotations

import contextlib
import logging
import mmap
import os
import re
import struct
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from .paths import logs_dir

_LOG_READY = False

# Machine values from the PE COFF header.
PE_MACHINE_X32 = 0x014C
PE_MACHINE_X64 = 0x8664
PE_MACHINE_ARM64 = 0xAA64

_ARCH_BY_MACHINE = {
    PE_MACHINE_X32: "x32",
    PE_MACHINE_X64: "x64",
    PE_MACHINE_ARM64: "arm64",
}

# Names that are almost never the game binary itself.
_EXE_SKIP_PATTERNS = (
    "unins",
    "setup",
    "install",
    "vcredist",
    "dxsetup",
    "dxwebsetup",
    "dotnetfx",
    "redist",
    "crashhandler",
    "crashreport",
    "report",
    "launcher_installer",
    "python",
    "node",
    "easyanticheat",
    "beservice",
    "battleye",
)


def _harden_console() -> None:
    """Never let a game name with an exotic glyph kill the process.

    Windows consoles still default to a legacy code page in many setups, so
    stdout/stderr are switched to UTF-8 when possible and told to replace
    unencodable characters instead of raising UnicodeEncodeError.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            try:
                stream.reconfigure(errors="replace")  # type: ignore[union-attr]
            except (AttributeError, ValueError, OSError):
                pass


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure a rotating log file plus stderr output (idempotent)."""
    global _LOG_READY
    _harden_console()
    logger = logging.getLogger("dxvk_toolkit")
    if _LOG_READY:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    stream.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(stream)
    try:
        handler = RotatingFileHandler(
            logs_dir() / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(fmt)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
    except OSError:
        pass
    _LOG_READY = True
    return logger


log = logging.getLogger("dxvk_toolkit")


def human_size(num: float | int | None) -> str:
    if not num:
        return "-"
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def human_age(timestamp: float | None) -> str:
    if not timestamp:
        return "never"
    delta = max(0.0, time.time() - float(timestamp))
    if delta < 90:
        return "just now"
    if delta < 5400:
        return f"{delta / 60:.0f} min ago"
    if delta < 172800:
        return f"{delta / 3600:.0f} h ago"
    return f"{delta / 86400:.0f} d ago"


def safe_name(name: str) -> str:
    """Turn an arbitrary version string into a safe folder name."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", str(name)).strip(" .")
    return cleaned or "unknown"


def parse_version_tuple(text: str) -> tuple[int, ...]:
    """Extract a comparable numeric tuple from strings like v2.7.1-1."""
    numbers = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in numbers[:6]) if numbers else (0,)


def pe_machine(path: str | os.PathLike[str]) -> str | None:
    """Return x32/x64/arm64 for a PE file, or None when it is not a PE image."""
    try:
        with open(path, "rb") as fh:
            header = fh.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                return None
            (pe_offset,) = struct.unpack_from("<I", header, 0x3C)
            if pe_offset <= 0 or pe_offset > 0x10000000:
                return None
            fh.seek(pe_offset)
            coff = fh.read(6)
    except (OSError, struct.error):
        return None
    if len(coff) < 6 or coff[:4] != b"PE\0\0":
        return None
    (machine,) = struct.unpack_from("<H", coff, 4)
    return _ARCH_BY_MACHINE.get(machine)


def iter_executables(game_dir: str | os.PathLike[str], max_depth: int = 2) -> Iterator[Path]:
    """Yield .exe files under game_dir, shallowest first (sorted per level)."""
    root = Path(game_dir)

    def walk(directory: Path, depth: int) -> Iterator[Path]:
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        files = [p for p in entries if p.is_file() and p.suffix.lower() == ".exe"]
        yield from files
        if depth >= max_depth:
            return
        for entry in entries:
            if entry.is_dir() and not entry.name.startswith("."):
                yield from walk(entry, depth + 1)

    yield from walk(root, 0)


def guess_main_executable(game_dir: str | os.PathLike[str]) -> tuple[Path | None, str | None]:
    """Pick the most likely main game binary and return (path, architecture).

    Preference order: root level first, then nested folders; setup/redist
    helpers are skipped; the biggest remaining candidate wins, which matches
    how games are laid out in practice.
    """
    candidates: list[tuple[int, int, Path]] = []
    for index, exe in enumerate(iter_executables(game_dir)):
        lowered = exe.name.lower()
        if any(pattern in lowered for pattern in _EXE_SKIP_PATTERNS):
            continue
        try:
            size = exe.stat().st_size
        except OSError:
            continue
        try:
            depth = len(exe.relative_to(Path(game_dir)).parts) - 1
        except ValueError:
            depth = 0
        arch_rank = 0 if pe_machine(exe) else 1
        candidates.append((depth, arch_rank, exe, size))  # type: ignore[arg-type]
    if not candidates:
        # Fall back to any executable at all.
        for exe in iter_executables(game_dir, max_depth=1):
            try:
                return exe, pe_machine(exe)
            except OSError:
                continue
        return None, None
    best = min(candidates, key=lambda item: (item[0], item[1], -item[3]))
    return best[2], pe_machine(best[2])


@contextlib.contextmanager
def file_buffer(path: str | os.PathLike[str], threshold: int = 8_000_000) -> Iterator[Any]:
    """Yield a bytes-like view of a file, memory mapped when it is large.

    Game executables reach a few hundred megabytes; mapping avoids copying
    them while still allowing full-file searches.
    """
    try:
        handle = open(path, "rb")
    except OSError:
        yield b""
        return
    try:
        try:
            size = os.fstat(handle.fileno()).st_size
        except OSError:
            size = 0
        if size > threshold:
            try:
                mapped = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
            except (ValueError, OSError):
                yield handle.read()
            else:
                try:
                    yield mapped
                finally:
                    mapped.close()
        else:
            yield handle.read()
    finally:
        handle.close()


def pe_imports(
    path: str | os.PathLike[str], max_names: int = 512
) -> list[str]:
    """Lower-cased DLL names this PE image imports.

    Reading the import directory is a few kilobytes of IO per executable and
    tells us exactly which Direct3D runtime a game expects, without any online
    database. Failures degrade to an empty list.
    """
    with file_buffer(path) as data:
        return _pe_imports_from(data, max_names)


def _pe_imports_from(data: Any, max_names: int = 512) -> list[str]:
    if data is None or len(data) < 0x40 or bytes(data[:2]) != b"MZ":
        return []
    try:
        (pe_offset,) = struct.unpack_from("<I", data, 0x3C)
        if pe_offset <= 0 or pe_offset + 24 > len(data):
            return []
        if bytes(data[pe_offset : pe_offset + 4]) != b"PE\0\0":
            return []
        coff = pe_offset + 4
        (section_count,) = struct.unpack_from("<H", data, coff + 2)
        (optional_size,) = struct.unpack_from("<H", data, coff + 16)
        optional = coff + 20
        magic = struct.unpack_from("<H", data, optional)[0]
        if magic == 0x20B:  # PE32+
            directory_offset = optional + 112
        elif magic == 0x10B:  # PE32
            directory_offset = optional + 96
        else:
            return []
        import_rva, _import_size = struct.unpack_from("<II", data, directory_offset + 8)
        if import_rva == 0:
            return []
        sections = []
        section_table = optional + optional_size
        for index in range(section_count):
            base = section_table + index * 40
            if base + 40 > len(data):
                return []
            virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
                "<IIII", data, base + 8
            )
            sections.append((virtual_address, max(virtual_size, raw_size), raw_offset))
    except (struct.error, IndexError):
        return []

    def rva_to_offset(rva: int) -> int | None:
        for virtual_address, size, raw_offset in sections:
            if virtual_address <= rva < virtual_address + size:
                return raw_offset + (rva - virtual_address)
        return None

    names: list[str] = []
    offset = rva_to_offset(import_rva)
    if offset is None:
        return []
    while offset + 20 <= len(data) and len(names) < max_names:
        try:
            original, _timestamp, _forwarder, name_rva, first_thunk = struct.unpack_from(
                "<IIIII", data, offset
            )
        except struct.error:
            break
        if original == 0 and name_rva == 0 and first_thunk == 0:
            break
        name_offset = rva_to_offset(name_rva) if name_rva else None
        if name_offset is not None and name_offset < len(data):
            end = data.find(b"\0", name_offset, min(len(data), name_offset + 260))
            if end > name_offset:
                names.append(bytes(data[name_offset:end]).decode("ascii", "replace").lower())
        offset += 20
    return names


D3D_NAME_PATTERNS = (
    b"d3d12.dll",
    b"d3d11.dll",
    b"d3d10core.dll",
    b"d3d10.dll",
    b"d3d9.dll",
    b"d3d8.dll",
    b"dxgi.dll",
    b"ddraw.dll",
)


def d3d_name_hits(path: str | os.PathLike[str]) -> set[str]:
    """Direct3D DLL names mentioned anywhere in the file.

    Covers games that resolve Direct3D with LoadLibrary instead of a static
    import, which is common for launchers and engine wrappers.
    """
    hits: set[str] = set()
    with file_buffer(path) as data:
        if not data:
            return hits
        lowered = bytes(data).lower() if not isinstance(data, bytes) else data.lower()
        del data
        for pattern in D3D_NAME_PATTERNS:
            if pattern in lowered:
                hits.add(pattern.decode())
    return hits


# The DXVK banner sits 0.9-2.2 MB into the binary, so a real read is needed;
# results are memoised per file identity because the UI asks repeatedly.
_DXVK_PROBE_CACHE: dict[str, tuple[int, int, bool]] = {}


def looks_like_dxvk(path: str | os.PathLike[str], probe_bytes: int = 2_500_000) -> bool:
    """Cheap heuristic: DXVK binaries contain the DXVK version banner."""
    key = os.path.normcase(os.path.abspath(str(path)))
    try:
        info = os.stat(path)
    except OSError:
        return False
    cached = _DXVK_PROBE_CACHE.get(key)
    if cached is not None and cached[0] == int(info.st_mtime) and cached[1] == info.st_size:
        return cached[2]
    try:
        with open(path, "rb") as handle:
            data = handle.read(probe_bytes)
    except OSError:
        return False
    result = b"DXVK" in data
    _DXVK_PROBE_CACHE[key] = (int(info.st_mtime), info.st_size, result)
    return result


def clear_dxvk_probe_cache() -> None:
    _DXVK_PROBE_CACHE.clear()


def open_in_file_manager(path: str | os.PathLike[str]) -> None:
    """Open a folder (or select a file) in the platform file manager."""
    target = str(path)
    try:
        if os.name == "nt":
            if os.path.isfile(target):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(target)])
            else:
                os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
    except Exception:  # pragma: no cover - platform dependent
        log.warning("Could not open %s in the file manager", target)


def ensure_unique_dir_name(existing: Iterable[str], wanted: str) -> str:
    used = set(existing)
    if wanted not in used:
        return wanted
    index = 2
    while f"{wanted} ({index})" in used:
        index += 1
    return f"{wanted} ({index})"
