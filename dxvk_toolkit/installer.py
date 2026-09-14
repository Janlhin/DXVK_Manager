"""DLL planning plus install / backup / restore for a single game folder."""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .paths import ledger
from .sources import arch_bin_dir, list_dlls
from .steam import KNOWN_DLLS, guess_direct3d, scan_runtime_dlls
from .util import log, looks_like_dxvk, pe_machine

BACKUP_SUFFIX = ".bkp"
CONF_NAME = "dxvk.conf"

# Fallback when the Direct3D family cannot be determined.
DEFAULT_DLLS = ("d3d9.dll", "dxgi.dll", "d3d11.dll")


@dataclass
class DllPlan:
    required: list[str]
    description: str

    @property
    def summary(self) -> str:
        return f"{self.description} - {', '.join(self.required) if self.required else 'no DLLs'}"


@dataclass
class InstallResult:
    success: bool
    message: str
    copied: list[str] = field(default_factory=list)
    backed_up: list[str] = field(default_factory=list)
    missing_source: list[str] = field(default_factory=list)
    warning: str = ""


@dataclass
class RestoreResult:
    success: bool
    message: str
    restored: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class GameStatus:
    """Everything the UI needs to describe the current DXVK state of a folder."""

    install_dir: str
    patched: bool = False
    backuped: bool = False
    version: str = ""
    kind: str = ""
    timestamp: str = ""
    conf_present: bool = False
    dxvk_files: list[str] = field(default_factory=list)
    backup_files: list[str] = field(default_factory=list)
    arch: str = ""
    executable: str = ""

    @property
    def label(self) -> str:
        if self.patched and self.version:
            return f"{self.kind or 'dxvk'} {self.version}"
        if self.patched:
            return "patched (version unknown)"
        return "not patched"


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------

def dlls_for_direct3d(version: str | None) -> DllPlan:
    """Which DXVK DLLs to drop in, based on the game's Direct3D family."""
    text = (version or "").strip()
    if not text or text.lower() == "unknown":
        return DllPlan(list(DEFAULT_DLLS), "Unknown (using common DLLs)")

    lowered = text.lower()
    numbers = []
    for token in lowered.replace("-", " ").split():
        digits = "".join(ch for ch in token if ch.isdigit())
        if digits:
            numbers.append(int(digits))
    primary = numbers[0] if numbers else None

    if primary == 8 or "d3d8" in lowered or "direct3d 8" in lowered:
        return DllPlan(["d3d8.dll", "d3d9.dll"], "Direct3D 8")
    if primary == 9 or "d3d9" in lowered or "direct3d 9" in lowered:
        return DllPlan(["d3d9.dll"], "Direct3D 9")
    if primary == 10 or "d3d10" in lowered or "direct3d 10" in lowered:
        return DllPlan(["dxgi.dll", "d3d11.dll", "d3d10core.dll"], "Direct3D 10")
    if primary == 11 or "d3d11" in lowered or "direct3d 11" in lowered:
        return DllPlan(["dxgi.dll", "d3d11.dll"], "Direct3D 11")
    if primary == 12 or "d3d12" in lowered or "direct3d 12" in lowered:
        return DllPlan(["dxgi.dll", "d3d12.dll"], "Direct3D 12 (DXVK support is limited)")
    return DllPlan(list(DEFAULT_DLLS), "Unknown (using common DLLs)")


def choose_arch(game_dir: str | os.PathLike[str], override: str = "", executable: str = "") -> str:
    """Pick x64 or x32 for a game folder (PE header based, x64 by default)."""
    if override in ("x32", "x64"):
        return override
    if executable:
        arch = pe_machine(executable)
        if arch in ("x32", "x64"):
            return arch
    from .util import guess_main_executable

    _, arch = guess_main_executable(game_dir)
    return arch if arch in ("x32", "x64") else "x64"


def missing_dlls(game_dir: str | os.PathLike[str], required: Iterable[str]) -> list[str]:
    root = Path(game_dir)
    return [dll for dll in required if not (root / dll).is_file()]


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------

# Folder state is expensive to read (directory listing plus a 2 MB signature
# probe per DLL), and the UI asks for it on every repaint. Entries are keyed by
# the folder modification time, which changes whenever files are added or
# removed, so stale data is impossible in practice.
_STATUS_CACHE: dict[str, tuple[float, int, GameStatus]] = {}


def invalidate(game_dir: str | os.PathLike[str]) -> None:
    """Drop the cached state of one game folder after we touch it."""
    _STATUS_CACHE.pop(_cache_key(game_dir), None)


def _cache_key(game_dir: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(str(game_dir)))


def inspect(
    game_dir: str | os.PathLike[str], *, probe: bool = True, use_cache: bool = True
) -> GameStatus:
    """Read the on-disk state of a game folder (never raises).

    probe=False skips the DXVK signature reads and trusts the ledger, which is
    what the list view wants while scrolling; probe=True is used when the
    answer must be exact.
    """
    key = _cache_key(game_dir)
    if use_cache:
        cached = _STATUS_CACHE.get(key)
        if cached is not None and cached[1] == int(probe):
            try:
                if cached[0] == Path(game_dir).stat().st_mtime:
                    return cached[2]
            except OSError:
                pass

    status = _inspect_uncached(game_dir, probe)
    try:
        stamp = Path(game_dir).stat().st_mtime
    except OSError:
        stamp = 0.0
    _STATUS_CACHE[key] = (stamp, int(probe), status)
    return status


def _inspect_uncached(game_dir: str | os.PathLike[str], probe: bool) -> GameStatus:
    root = Path(game_dir)
    status = GameStatus(install_dir=str(root))
    record = ledger.get(root)
    if record:
        status.patched = bool(record.get("patched"))
        status.backuped = bool(record.get("backuped"))
        status.version = str(record.get("dxvk_version") or "")
        status.kind = str(record.get("dxvk_type") or "")
        status.timestamp = str(record.get("updated") or record.get("dxvk_timestamp") or "")
        status.arch = str(record.get("arch") or "")

    status.dxvk_files = []
    status.backup_files = []
    if probe:
        for dll in KNOWN_DLLS:
            path = root / dll
            if path.is_file() and looks_like_dxvk(path):
                status.dxvk_files.append(dll)
    elif status.patched:
        # Everything already in the ledger is reported as the last known DLLs.
        recorded = ledger.get(root).get("dlls")
        if isinstance(recorded, list):
            status.dxvk_files = [str(name) for name in recorded]
    try:
        status.backup_files = sorted(
            child.name[: -len(BACKUP_SUFFIX)]
            for child in root.iterdir()
            if child.is_file() and child.name.lower().endswith(BACKUP_SUFFIX)
        )
    except OSError:
        status.backup_files = []
    status.patched = bool(status.dxvk_files) or status.patched
    status.backuped = bool(status.backup_files) or status.backuped
    status.conf_present = (root / CONF_NAME).is_file()
    if not status.arch:
        status.arch = guess_arch_from_dxvk(status.dxvk_files)
    return status


def guess_arch_from_dxvk(dll_names: Iterable[str]) -> str:
    names = {name.lower() for name in dll_names}
    if "d3d11.dll" in names or "dxgi.dll" in names:
        return "x64"
    return ""


# --------------------------------------------------------------------------
# Mutating operations
# --------------------------------------------------------------------------

def _backup(root: Path, dll: str) -> bool:
    source = root / dll
    backup = root / (dll + BACKUP_SUFFIX)
    if not source.is_file() or backup.exists():
        return False
    shutil.copy2(source, backup)
    return True


def install(
    game_dir: str | os.PathLike[str],
    kind: str,
    version: str,
    *,
    arch: str = "",
    d3d_hint: str = "",
    dlls: Iterable[str] | None = None,
    conf_text: str | None = None,
    force_backup: bool = False,
) -> InstallResult:
    """Copy a cached DXVK version into a game folder, backing originals up."""
    root = Path(game_dir)
    if not root.is_dir():
        return InstallResult(False, f"Game folder not found: {root}")

    plan = dlls_for_direct3d(d3d_hint or guess_direct3d(root))
    wanted = list(dlls) if dlls else list(plan.required)
    chosen_arch = choose_arch(root, arch)

    bin_dir = arch_bin_dir(kind, version, chosen_arch)
    if bin_dir is None:
        return InstallResult(
            False,
            f"{kind} {version} is not downloaded yet (or has no {chosen_arch} folder)",
        )

    status = inspect(root)
    copied: list[str] = []
    backed_up: list[str] = []
    missing_source: list[str] = []

    for dll in wanted:
        source = bin_dir / dll
        if not source.is_file():
            missing_source.append(dll)
            continue
        already_patched = dll in status.dxvk_files
        if not already_patched or force_backup:
            if _backup(root, dll):
                backed_up.append(dll)
        try:
            shutil.copy2(source, root / dll)
            copied.append(dll)
        except OSError as exc:
            return InstallResult(False, f"Could not copy {dll}: {exc}", copied, backed_up)

    if not copied:
        return InstallResult(
            False,
            "No DLLs were copied - the cached version does not provide "
            f"{', '.join(wanted)} for {chosen_arch}",
            copied,
            backed_up,
            missing_source,
        )

    if dlls:
        backups = True
    else:
        backups = bool(backed_up) or status.backuped

    ledger.record(
        root,
        patched=True,
        backuped=backups,
        dxvk_version=version,
        dxvk_type=kind,
        dxvk_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        arch=chosen_arch,
        dlls=copied,
    )

    if conf_text is not None:
        write_conf(root, conf_text)

    warning = ""
    absent = missing_dlls(root, wanted)
    if absent and not status.dxvk_files:
        warning = (
            "None of the original Direct3D DLLs were present in the game folder. "
            "DXVK will still be installed, but the game may not use it."
        )
    invalidate(root)
    message = f"Installed {kind} {version} ({chosen_arch}) - {len(copied)} file(s)"
    if missing_source:
        message += f"; not shipped by this build: {', '.join(missing_source)}"
    log.info("%s -> %s", message, root)
    return InstallResult(True, message, copied, backed_up, missing_source, warning)


def restore(game_dir: str | os.PathLike[str], dlls: Iterable[str] | None = None) -> RestoreResult:
    """Put the backed up originals back and drop the DXVK copies."""
    root = Path(game_dir)
    if not root.is_dir():
        return RestoreResult(False, f"Game folder not found: {root}")

    status = inspect(root)
    wanted = list(dlls) if dlls else sorted(set(status.backup_files) | set(status.dxvk_files))
    if not wanted:
        wanted = list(dlls_for_direct3d(guess_direct3d(root)).required)

    restored: list[str] = []
    failed: list[str] = []

    for dll in wanted:
        backup = root / (dll + BACKUP_SUFFIX)
        target = root / dll
        if not backup.is_file():
            continue
        try:
            if target.exists():
                target.unlink()
            backup.rename(target)
            restored.append(dll)
        except OSError as exc:
            log.warning("restore failed for %s: %s", dll, exc)
            failed.append(dll)

    if not restored:
        return RestoreResult(False, "No backups were found to restore", restored, failed)

    invalidate(root)
    remaining_backups = any(
        child.name.lower().endswith(BACKUP_SUFFIX) for child in root.iterdir() if child.is_file()
    )
    ledger.record(
        root,
        patched=bool(inspect(root).dxvk_files),
        backuped=remaining_backups,
        dxvk_version="" if not remaining_backups else ledger.get(root).get("dxvk_version", ""),
        dxvk_type="" if not remaining_backups else ledger.get(root).get("dxvk_type", ""),
    )
    message = f"Restored {len(restored)} original file(s)"
    if failed:
        message += f"; {len(failed)} failed"
    return RestoreResult(True, message, restored, failed)


def remove_dxvk(game_dir: str | os.PathLike[str], dlls: Iterable[str] | None = None) -> list[str]:
    """Delete the DXVK DLLs without touching the backups."""
    root = Path(game_dir)
    status = inspect(root)
    wanted = list(dlls) if dlls else (status.dxvk_files or list(DEFAULT_DLLS))
    removed: list[str] = []
    for dll in wanted:
        path = root / dll
        if path.is_file():
            try:
                path.unlink()
                removed.append(dll)
            except OSError as exc:
                log.warning("could not remove %s: %s", path, exc)
    if removed:
        ledger.record(root, patched=False, dxvk_version="", dxvk_type="")
        invalidate(root)
    return removed


def write_conf(game_dir: str | os.PathLike[str], text: str, name: str = CONF_NAME) -> Path:
    """Write a dxvk.conf next to the game executable.

    An existing file is kept as <name>.bkp first: the user's own tweaks are
    worth more than the convenience of overwriting silently.
    """
    root = Path(game_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / name
    if target.is_file():
        try:
            shutil.copy2(target, target.with_suffix(target.suffix + ".bkp"))
        except OSError as exc:
            log.debug("could not back up %s: %s", target, exc)
    target.write_text(text, encoding="utf-8", newline="\r\n")
    ledger.record(root, conf_written=time.strftime("%Y-%m-%d %H:%M:%S"), conf_path=str(target))
    invalidate(root)
    return target


def read_conf(game_dir: str | os.PathLike[str], name: str = CONF_NAME) -> str:
    target = Path(game_dir) / name
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def delete_conf(game_dir: str | os.PathLike[str], name: str = CONF_NAME) -> bool:
    target = Path(game_dir) / name
    try:
        target.unlink()
        return True
    except OSError:
        return False
