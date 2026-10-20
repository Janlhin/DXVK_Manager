"""Offline Direct3D family and architecture detection for a game folder.

Split out of :mod:`dxvk_toolkit.steam`: discovery answers "which games are
installed", detection answers "what does this folder need". The installer only
depends on the latter, so it imports from here instead of the discovery module.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .paths import data_root
from .util import (
    biggest_executable,
    d3d_name_hits,
    iter_executables,
    log,
    pe_imports,
    pe_machine,
    resolve_dll_dir,
)

# Direct3D runtime DLLs a game might ship or that DXVK can replace.
KNOWN_DLLS = (
    "d3d8.dll",
    "d3d9.dll",
    "d3d10core.dll",
    "d3d11.dll",
    "d3d12.dll",
    "dxgi.dll",
)

# --------------------------------------------------------------------------
# Local inspection
# --------------------------------------------------------------------------

def scan_runtime_dlls(game_dir: str | os.PathLike[str]) -> dict[str, bool]:
    """Which Direct3D DLLs are present next to the game executable.

    The install root alone is not enough: plenty of games load their runtime
    from a subdirectory (Watch_Dogs2/bin, ...), so the lookup follows the main
    executable like every DLL operation does.
    """

    root = Path(game_dir)
    dll_dir = resolve_dll_dir(root, KNOWN_DLLS)
    presence: dict[str, bool] = {}
    for dll in KNOWN_DLLS:
        try:
            presence[dll] = (dll_dir / dll).is_file()
        except OSError:
            presence[dll] = False
    return presence


def guess_direct3d(game_dir: str | os.PathLike[str], presence: dict[str, bool] | None = None) -> str:
    """Guess the Direct3D family from the DLLs a game ships.

    Import tables would be more precise but require parsing every executable;
    the shipped runtime DLLs are an excellent proxy and cost nothing.
    """
    found = presence if presence is not None else scan_runtime_dlls(game_dir)
    if found.get("d3d12.dll"):
        return "Direct3D 12"
    if found.get("d3d11.dll"):
        return "Direct3D 11"
    if found.get("d3d10core.dll"):
        return "Direct3D 10"
    if found.get("d3d9.dll"):
        return "Direct3D 9"
    if found.get("d3d8.dll"):
        return "Direct3D 8"
    if found.get("dxgi.dll"):
        return "Direct3D 10/11"
    return "Unknown"


# Ranking used when several Direct3D families show up in one game.
_D3D_RANKING = (
    ("Direct3D 12", ("d3d12.dll",)),
    ("Direct3D 11", ("d3d11.dll",)),
    ("Direct3D 10", ("d3d10core.dll", "d3d10.dll")),
    ("Direct3D 9", ("d3d9.dll",)),
    ("Direct3D 8", ("d3d8.dll", "ddraw.dll")),
)


# Agility SDK / D3D12-on-7 deployment markers: a game shipping these is a
# Direct3D 12 title even when its executable is packed or resolves Direct3D
# through a launcher.
_D3D12_MARKERS = ("d3d12core.dll", "d3d12sdklayers.dll", "d3d12.dll")


def _rank_d3d(names: set[str]) -> str:
    for label, modules in _D3D_RANKING:
        if any(module in names for module in modules):
            return label
    if "dxgi.dll" in names:
        return "Direct3D 10/11"
    return ""


def _has_d3d12_marker(root: Path, max_depth: int = 3) -> bool:
    """Look for the D3D12 Agility SDK files that ship with D3D12 games."""
    stack: list[tuple[Path, int]] = [(root, 0)]
    visited = 0
    while stack and visited < 400:
        directory, depth = stack.pop()
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            visited += 1
            try:
                if entry.is_dir():
                    if depth < max_depth and not entry.name.startswith("."):
                        stack.append((entry, depth + 1))
                elif entry.name.lower() in _D3D12_MARKERS:
                    return True
            except OSError:
                continue
    return False


def detect_direct3d(
    game_dir: str | os.PathLike[str],
    presence: dict[str, bool] | None = None,
    *,
    max_executables: int = 5,
) -> str:
    """Best-effort Direct3D family for a game folder, fully offline.

    Signal strength, strongest first:
      1. the Direct3D runtime DLLs the game ships in its root folder,
      2. D3D12 Agility SDK marker files (packed executables still ship these),
      3. the import table of the main executable,
      4. the import tables of the remaining executables,
      5. module names mentioned inside those executables (dynamic loading).
    Raw string hits are used last because engines often mention a Direct3D
    module they only use on a secondary code path.
    """

    found = presence if presence is not None else scan_runtime_dlls(game_dir)
    if any(found.values()):
        return guess_direct3d(game_dir, found)

    root = Path(game_dir)
    if _has_d3d12_marker(root):
        return "Direct3D 12"

    main_exe = biggest_executable(root)
    others: list[Path] = []
    for exe in iter_executables(root, max_depth=3):
        if main_exe is not None and exe == main_exe:
            continue
        lowered = exe.name.lower()
        if any(pattern in lowered for pattern in _D3D_SKIP_EXE):
            continue
        others.append(exe)
        if len(others) >= max_executables * 4:
            break
    folder_hint = root.name.lower().replace(" ", "")[:8]
    others.sort(
        key=lambda path: (
            0 if path.name.lower().replace(" ", "").startswith(folder_hint) else 1,
            -_safe_size(path),
        )
    )
    candidates = ([main_exe] if main_exe is not None else []) + others[:max_executables]
    if not candidates:
        return "Unknown"

    if main_exe is not None:
        ranked = _rank_d3d(set(pe_imports(main_exe)))
        if ranked:
            return ranked

    imported: set[str] = set()
    for exe in candidates:
        imported.update(pe_imports(exe))
    ranked = _rank_d3d(imported)
    if ranked:
        return ranked

    mentioned: set[str] = set()
    for exe in candidates:
        mentioned.update(d3d_name_hits(exe))
    return _rank_d3d(mentioned) or "Unknown"


_D3D_SKIP_EXE = (
    "vcredist",
    "dxsetup",
    "dxwebsetup",
    "unins",
    "setup",
    "install",
    "crashreport",
    "crashhandler",
    "easyanticheat",
    "beservice",
    "battleye",
    "redist",
    "dotnetfx",
    "report",
)


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def detect_arch(game_dir: str | os.PathLike[str]) -> str:
    """x32/x64 of the game's main executable, or an empty string."""

    exe = biggest_executable(game_dir)
    if exe is not None:
        arch = pe_machine(exe)
        if arch in ("x32", "x64"):
            return arch
    # Fall back to any executable we can read a header from.
    for candidate in iter_executables(game_dir, max_depth=1):
        found = pe_machine(candidate)
        if found in ("x32", "x64"):
            return found
    return ""


# --------------------------------------------------------------------------
# Detection cache
# --------------------------------------------------------------------------

_DETECT_CACHE: dict[str, dict[str, str]] | None = None
# Two detection workers may describe games concurrently and both persist the
# cache; serialising load/flush keeps json.dumps from iterating a dict that is
# being mutated ("dictionary changed size during iteration").
_DETECT_LOCK = threading.Lock()


def _detect_cache_file() -> Path:

    folder = data_root() / "cache"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "detection.json"


def _load_detect_cache() -> dict[str, dict[str, str]]:
    global _DETECT_CACHE

    with _DETECT_LOCK:
        if _DETECT_CACHE is not None:
            return _DETECT_CACHE

        try:
            payload = json.loads(_detect_cache_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        _DETECT_CACHE = payload if isinstance(payload, dict) else {}
        return _DETECT_CACHE


def _folder_stamp(game_dir: str | os.PathLike[str]) -> str:
    """Invalidation signal for a detection cache entry.

    The root's mtime alone is not enough: the DLLs live next to the
    executable, often in a subdirectory, and writing or removing them does
    not touch the root - the old stamp kept stale "Unknown/x32" detections
    alive forever. The directory the DLLs resolve to is folded in, so its
    changes invalidate the entry as well.
    """

    try:
        parts = [str(int(Path(game_dir).stat().st_mtime))]
    except OSError:
        return "0"
    root = Path(game_dir)
    dll_dir = resolve_dll_dir(root, KNOWN_DLLS)
    if dll_dir != root:
        try:
            parts.append(str(int(dll_dir.stat().st_mtime)))
        except OSError:
            pass
    return ":".join(parts)


def flush_detect_cache() -> None:
    """Persist the detection cache once after a batch of describe_game calls."""

    with _DETECT_LOCK:
        if _DETECT_CACHE is None:
            return
        try:
            payload = json.dumps(_DETECT_CACHE, indent=1)
        except (TypeError, ValueError) as exc:
            log.debug("could not serialise detection cache: %s", exc)
            return
    try:
        _detect_cache_file().write_text(payload, encoding="utf-8")
    except OSError as exc:
        log.debug("could not persist detection cache: %s", exc)


def describe_game(
    game_dir: str | os.PathLike[str], *, use_cache: bool = True, persist: bool = True
) -> dict[str, str]:
    """Cached {direct3d, arch} description of a game folder.

    The folder modification time invalidates the entry, so a reinstalled or
    patched game is re-detected automatically.
    """

    path = Path(game_dir)
    key = os.path.normcase(os.path.abspath(str(path)))
    stamp = _folder_stamp(path)
    cache = _load_detect_cache()
    entry = cache.get(key)
    if use_cache and isinstance(entry, dict) and entry.get("stamp") == stamp and entry.get("d3d"):
        return {"direct3d": str(entry.get("d3d") or ""), "arch": str(entry.get("arch") or "")}

    presence = scan_runtime_dlls(path)
    d3d = detect_direct3d(path, presence)
    arch = detect_arch(path)
    entry = {"stamp": stamp, "d3d": d3d, "arch": arch,
             "shipped": ",".join(sorted(k for k, v in presence.items() if v))}
    with _DETECT_LOCK:
        cache[key] = entry
    if persist:
        flush_detect_cache()
    return {"direct3d": d3d, "arch": arch}


