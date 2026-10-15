"""Game discovery across launchers: Steam library parsing plus the Epic
Games Launcher, GOG and Ubisoft Connect registries.

The original Electron application only looked at one hardcoded path. This
module walks every Steam library listed in libraryfolders.vdf, understands
the Unicode-escaped quoted format Valve uses, and reads the other launchers'
install manifests/registries so a machine's whole library shows up. Manual
(non-launcher) folders stay first-class citizens because the config
generator is useful for them too.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import net
from .paths import data_root
from .util import iter_executables, log

# Direct3D runtime DLLs a game might ship or that DXVK can replace.
KNOWN_DLLS = (
    "d3d8.dll",
    "d3d9.dll",
    "d3d10core.dll",
    "d3d11.dll",
    "d3d12.dll",
    "dxgi.dll",
)

_BACKUP_SUFFIX = ".bkp"

# Platforms the scanner can report. Labels are used by the UI.
PLATFORM_LABELS = {
    "steam": "Steam",
    "epic": "Epic",
    "gog": "GOG",
    "ubisoft": "Ubisoft",
    "battlenet": "Battle.net",
    "riot": "Riot",
    "wegame": "WeGame",
    "mihoyo": "米哈游",
    "ea": "EA",
    "itch": "itch.io",
    "manual": "手动添加",
}


@dataclass
class Game:
    """One installed game, either discovered through Steam or added by hand."""

    appid: str
    name: str
    install_dir: Path
    library_dir: Path | None = None
    size_on_disk: int = 0
    state_flags: int = 0
    source: str = "steam"
    cover_url: str = ""

    @property
    def key(self) -> str:
        return os.path.normcase(os.path.abspath(str(self.install_dir)))

    @property
    def exists(self) -> bool:
        try:
            return self.install_dir.is_dir()
        except OSError:
            return False

    @property
    def is_fully_installed(self) -> bool:
        if self.source != "steam":
            return self.exists
        # 4 == fully installed in Valve's StateFlags bitfield.
        return bool(self.state_flags & 4) or self.exists

    def to_dict(self) -> dict[str, Any]:
        return {
            "appid": self.appid,
            "name": self.name,
            "install_dir": str(self.install_dir),
            "library_dir": str(self.library_dir) if self.library_dir else "",
            "size_on_disk": self.size_on_disk,
            "state_flags": self.state_flags,
            "source": self.source,
            "cover_url": self.cover_url,
        }

    @property
    def platform_label(self) -> str:
        return PLATFORM_LABELS.get(self.source, self.source.title())

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Game:
        return cls(
            appid=str(payload.get("appid") or "manual"),
            name=str(payload.get("name") or Path(str(payload.get("install_dir", ""))).name),
            install_dir=Path(str(payload.get("install_dir") or "")),
            library_dir=Path(str(payload["library_dir"])) if payload.get("library_dir") else None,
            size_on_disk=int(payload.get("size_on_disk") or 0),
            state_flags=int(payload.get("state_flags") or 0),
            source=str(payload.get("source") or "manual"),
            cover_url=str(payload.get("cover_url") or ""),
        )


# --------------------------------------------------------------------------
# Valve keyvalues format
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])')


def _unescape(value: str) -> str:
    return value.replace("\\\\", "\\").replace('\\"', '"')


def parse_keyvalues(text: str) -> dict[str, Any]:
    """Parse a Valve keyvalues document into nested dicts.

    Only the subset Valve uses for manifests is supported: quoted keys, quoted
    values and nested blocks. Backslash escapes are decoded.
    """
    tokens: list[Any] = []
    for match in _TOKEN_RE.finditer(text):
        if match.group(1) is not None:
            tokens.append(("value", _unescape(match.group(1))))
        else:
            tokens.append(("brace", match.group(2)))

    root: dict[str, Any] = {}
    stack: list[dict[str, Any]] = [root]
    pending_key: str | None = None

    for kind, token in tokens:
        current = stack[-1]
        if kind == "value":
            if pending_key is None:
                pending_key = token
            else:
                current[pending_key] = token
                pending_key = None
        elif token == "{":
            child: dict[str, Any] = {}
            if pending_key is not None:
                current[pending_key] = child
                pending_key = None
            stack.append(child)
        else:  # closing brace
            if len(stack) > 1:
                stack.pop()
            pending_key = None
    return root


# --------------------------------------------------------------------------
# Steam discovery
# --------------------------------------------------------------------------

def _registry_steam_paths() -> list[Path]:
    if os.name != "nt":
        return []
    paths: list[Path] = []
    try:
        import winreg  # noqa: WPS433
    except ImportError:
        return paths
    candidates = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    for hive, subkey, value_name in candidates:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
            if value:
                paths.append(Path(str(value)))
        except (OSError, ValueError):
            continue
    return paths


def _default_steam_paths() -> list[Path]:
    if os.name != "nt":
        return [Path.home() / ".steam" / "steam", Path.home() / ".local/share/Steam"]
    return [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path(r"D:\Steam"),
        Path(r"D:\SteamLibrary"),
        Path(r"E:\Steam"),
        Path(r"E:\SteamLibrary"),
    ]


def steam_root() -> Path | None:
    """Best guess for the Steam installation directory."""
    for candidate in _registry_steam_paths() + _default_steam_paths():
        try:
            if (candidate / "steamapps").is_dir() or (candidate / "steam.exe").is_file():
                return candidate
        except OSError:
            continue
    return None


def library_folders(extra: Iterable[str] = ()) -> list[Path]:
    """Every Steam library folder, including extra user-configured ones."""
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            key = os.path.normcase(os.path.abspath(str(path)))
        except OSError:
            return
        if key in seen:
            return
        seen.add(key)
        found.append(path)

    root = steam_root()
    if root is not None:
        add(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                data = parse_keyvalues(vdf.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                data = {}
            entries = data.get("libraryfolders") or data.get("LibraryFolders") or {}
            if isinstance(entries, dict):
                for value in entries.values():
                    if isinstance(value, dict) and value.get("path"):
                        add(Path(str(value["path"])))
                    elif isinstance(value, str) and os.path.isabs(value):
                        add(Path(value))
    for extra_path in extra:
        if extra_path:
            add(Path(extra_path))
    log.debug("Steam libraries: %s", [str(p) for p in found])
    return found


def _read_manifest(path: Path) -> Game | None:
    try:
        data = parse_keyvalues(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    state = data.get("AppState") if isinstance(data.get("AppState"), dict) else data
    if not isinstance(state, dict):
        return None
    appid = str(state.get("appid") or "").strip()
    name = str(state.get("name") or "").strip()
    installdir = str(state.get("installdir") or "").strip()
    if not appid or not installdir:
        return None
    library = path.parent.parent
    try:
        state_flags = int(str(state.get("StateFlags") or "0"))
    except ValueError:
        state_flags = 0
    try:
        size = int(str(state.get("SizeOnDisk") or "0"))
    except ValueError:
        size = 0
    return Game(
        appid=appid,
        name=name or installdir,
        install_dir=library / "steamapps" / "common" / installdir,
        library_dir=library,
        size_on_disk=size,
        state_flags=state_flags,
        source="steam",
    )


def scan_steam_games(extra_libraries: Iterable[str] = ()) -> list[Game]:
    """All Steam games that have an appmanifest in any known library."""
    games: list[Game] = []
    seen: set[str] = set()
    for library in library_folders(extra_libraries):
        steamapps = library / "steamapps"
        if not steamapps.is_dir():
            continue
        try:
            manifests = sorted(steamapps.glob("appmanifest_*.acf"))
        except OSError:
            continue
        for manifest in manifests:
            game = _read_manifest(manifest)
            if game is None or game.key in seen:
                continue
            seen.add(game.key)
            games.append(game)
    games.sort(key=lambda g: g.name.lower())
    return games


def game_from_folder(folder: str | os.PathLike[str], name: str = "") -> Game:
    path = Path(folder)
    return Game(
        appid="manual",
        name=name or path.name,
        install_dir=path,
        source="manual",
    )


# --------------------------------------------------------------------------
# Other launchers: Epic, GOG, Ubisoft
# --------------------------------------------------------------------------

def _epic_manifest_dir() -> Path | None:
    """Where the Epic Games Launcher stores its installed-game manifests."""
    candidates = (
        Path(os.environ.get("ProgramData", r"C:\ProgramData"))
        / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests",
        Path(r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests"),
    )
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


def _read_epic_manifest(path: Path) -> Game | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("bIsIncomplete"):
        return None
    install = str(data.get("InstallLocation") or "").strip()
    name = str(data.get("DisplayName") or "").strip()
    if not install or not name:
        return None
    appid = (
        str(data.get("CatalogItemId") or "").strip()
        or str(data.get("AppName") or "").strip()
        or path.stem
    )
    return Game(appid=appid, name=name, install_dir=Path(install), source="epic")


def scan_epic_games(manifest_dir: str | os.PathLike[str] | None = None) -> list[Game]:
    """Epic Games Launcher titles from their .item manifests."""
    directory = Path(manifest_dir) if manifest_dir is not None else _epic_manifest_dir()
    if directory is None:
        return []
    try:
        manifests = sorted(directory.glob("*.item"))
    except OSError:
        return []
    games: list[Game] = []
    seen: set[str] = set()
    for manifest in manifests:
        game = _read_epic_manifest(manifest)
        if game is None or game.key in seen:
            continue
        seen.add(game.key)
        games.append(game)
    return games


def _registry_subkey_values(hive: int, subkey_path: str) -> list[tuple[str, dict[str, str]]]:
    """String values of every subkey below subkey_path. Empty off-Windows.

    Kept data-only (no Game construction) so the per-launcher mappers stay
    testable without a registry.
    """
    if os.name != "nt":
        return []
    try:
        import winreg  # noqa: WPS433
    except ImportError:
        return []
    entries: list[tuple[str, dict[str, str]]] = []
    try:
        with winreg.OpenKey(hive, subkey_path) as root:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                try:
                    with winreg.OpenKey(root, name) as child:
                        values: dict[str, str] = {}
                        value_index = 0
                        while True:
                            try:
                                value_name, value, _kind = winreg.EnumValue(child, value_index)
                            except OSError:
                                break
                            value_index += 1
                            if isinstance(value, str):
                                values[value_name] = value
                            elif isinstance(value, int):
                                values[value_name] = str(value)
                        entries.append((name, values))
                except OSError:
                    continue
    except OSError:
        return entries
    return entries


def _gog_games_from_entries(entries: list[tuple[str, dict[str, str]]]) -> list[Game]:
    games: list[Game] = []
    for key_name, values in entries:
        install = str(values.get("path") or "").strip()
        if not install:
            continue
        name = str(values.get("gameName") or "").strip() or Path(install).name
        games.append(Game(appid=key_name, name=name, install_dir=Path(install), source="gog"))
    return games


def scan_gog_games() -> list[Game]:
    """GOG titles (Galaxy or offline installers) from the shared registry tree."""
    if os.name != "nt":
        return []
    import winreg  # noqa: WPS433

    entries = _registry_subkey_values(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games"
    )
    entries += _registry_subkey_values(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GOG.com\Games")
    games: list[Game] = []
    seen: set[str] = set()
    for game in _gog_games_from_entries(entries):
        if game.key in seen:
            continue
        seen.add(game.key)
        games.append(game)
    return games


def _ubisoft_games_from_entries(entries: list[tuple[str, dict[str, str]]]) -> list[Game]:
    games: list[Game] = []
    seen: set[str] = set()
    for _key_name, values in entries:
        install = str(values.get("InstallDir") or "").strip().strip('"')
        if not install:
            continue
        path = Path(install)
        try:
            key = os.path.normcase(os.path.abspath(install))
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        games.append(Game(appid=path.name.lower(), name=path.name, install_dir=path,
                          source="ubisoft"))
    return games


def scan_ubisoft_games() -> list[Game]:
    """Ubisoft Connect titles from the launcher's registry install table."""
    if os.name != "nt":
        return []
    import winreg  # noqa: WPS433

    entries = _registry_subkey_values(
        winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"
    )
    return _ubisoft_games_from_entries(entries)


# HoYoPlay biz ids whose display names are stable across install paths.
# Anything unknown falls back to the install folder's name.
_MIHOYO_GAME_NAMES = {
    "hk4e_cn": "原神",
    "hkrpg_cn": "崩坏：星穹铁道",
    "nap_cn": "绝区零",
    "hglb_cn": "未定事件簿",
}


def _mihoyo_games_from_entries(entries: list[tuple[str, dict[str, str]]]) -> list[Game]:
    games: list[Game] = []
    seen: set[str] = set()
    for key_name, values in entries:
        install = str(values.get("GameInstallPath") or "").strip()
        if not install:
            continue
        path = Path(install)
        try:
            key = os.path.normcase(os.path.abspath(install))
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        name = _MIHOYO_GAME_NAMES.get(key_name) or path.name
        games.append(Game(appid=key_name, name=name, install_dir=path, source="mihoyo"))
    return games


def scan_mihoyo_games() -> list[Game]:
    """HoYoPlay-installed games (原神 / 星穹铁道 / 绝区零…) from their
    per-title registry records under HKCU\\Software\\miHoYo\\HYP."""
    if os.name != "nt":
        return []
    import winreg  # noqa: WPS433

    entries = _registry_subkey_values(winreg.HKEY_CURRENT_USER, r"Software\miHoYo\HYP\1_1")
    return _mihoyo_games_from_entries(entries)


def _wegame_games_from_entries(entries: list[tuple[str, dict[str, str]]]) -> list[Game]:
    """Every HKCU\\Software\\Tencent\\{app} record carrying both an
    InstallLocation and a DisplayName is a WeGame/rail game (无畏契约…);
    QQ/DeskGo and friends have neither and drop out naturally."""
    games: list[Game] = []
    seen: set[str] = set()
    for key_name, values in entries:
        install = str(values.get("InstallLocation") or "").strip()
        name = str(values.get("DisplayName") or "").strip()
        if not install or not name:
            continue
        path = Path(install)
        try:
            key = os.path.normcase(os.path.abspath(install))
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        games.append(Game(appid=str(values.get("ManifestId") or key_name), name=name,
                          install_dir=path, source="wegame"))
    return games


def scan_wegame_games() -> list[Game]:
    """WeGame / rail titles from their per-app HKCU registry records."""
    if os.name != "nt":
        return []
    import winreg  # noqa: WPS433

    entries = _registry_subkey_values(winreg.HKEY_CURRENT_USER, r"Software\Tencent")
    return _wegame_games_from_entries(entries)


def scan_all_games(extra_libraries: Iterable[str] = ()) -> list[Game]:
    """Every installed game we can discover.

    Steam first (richest names and covers), then Epic, GOG, Ubisoft,
    WeGame and miHoYo; duplicates by install folder are dropped so a game
    registered by two launchers appears once.
    """
    games: list[Game] = []
    seen: set[str] = set()
    for game in (
        scan_steam_games(extra_libraries)
        + scan_epic_games()
        + scan_gog_games()
        + scan_ubisoft_games()
        + scan_wegame_games()
        + scan_mihoyo_games()
    ):
        if game.key in seen:
            continue
        seen.add(game.key)
        games.append(game)
    games.sort(key=lambda g: g.name.lower())
    return games


# --------------------------------------------------------------------------
# Local inspection
# --------------------------------------------------------------------------

def scan_runtime_dlls(game_dir: str | os.PathLike[str]) -> dict[str, bool]:
    """Which Direct3D DLLs are present next to the game executable.

    The install root alone is not enough: plenty of games load their runtime
    from a subdirectory (Watch_Dogs2/bin, ...), so the lookup follows the main
    executable like every DLL operation does.
    """
    from .util import resolve_dll_dir

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
    from .util import d3d_name_hits, guess_main_executable, pe_imports

    found = presence if presence is not None else scan_runtime_dlls(game_dir)
    if any(found.values()):
        return guess_direct3d(game_dir, found)

    root = Path(game_dir)
    if _has_d3d12_marker(root):
        return "Direct3D 12"

    main_exe, _main_arch = guess_main_executable(root)
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
    from .util import guess_main_executable, pe_machine

    exe, arch = guess_main_executable(game_dir)
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


def _detect_cache_file() -> Path:

    folder = data_root() / "cache"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "detection.json"


def _load_detect_cache() -> dict[str, dict[str, str]]:
    global _DETECT_CACHE
    if _DETECT_CACHE is not None:
        return _DETECT_CACHE
    import json

    try:
        payload = json.loads(_detect_cache_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = {}
    _DETECT_CACHE = payload if isinstance(payload, dict) else {}
    return _DETECT_CACHE


def _folder_stamp(game_dir: str | os.PathLike[str]) -> str:
    try:
        return str(int(Path(game_dir).stat().st_mtime))
    except OSError:
        return "0"


def flush_detect_cache() -> None:
    """Persist the detection cache once after a batch of describe_game calls."""
    import json

    if _DETECT_CACHE is None:
        return
    try:
        _detect_cache_file().write_text(json.dumps(_DETECT_CACHE, indent=1), encoding="utf-8")
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
    cache[key] = {"stamp": stamp, "d3d": d3d, "arch": arch,
                  "shipped": ",".join(sorted(k for k, v in presence.items() if v))}
    if persist:
        flush_detect_cache()
    return {"direct3d": d3d, "arch": arch}

def has_backups(game_dir: str | os.PathLike[str]) -> bool:
    try:
        root = Path(game_dir)
        return any(child.suffix.lower() == _BACKUP_SUFFIX for child in root.iterdir())
    except OSError:
        return False


# --- Chinese store names -------------------------------------------------
# The Steam manifest only carries the English name, so searching for
# 巫师3 finds nothing. The store API knows the localized name; it is
# fetched once per game and kept on disk.

_NAMES: dict[str, str] | None = None


def _names_file() -> Path:
    return data_root() / "steam-names.json"


def load_names() -> dict[str, str]:
    """Cached appid -> localized name, loaded once."""
    global _NAMES
    if _NAMES is None:
        try:
            raw = json.loads(_names_file().read_text(encoding="utf-8"))
            _NAMES = {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            _NAMES = {}
    return _NAMES


def save_names() -> None:
    if _NAMES is None:
        return
    try:
        _names_file().write_text(json.dumps(_NAMES, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    except OSError as exc:
        log.debug("could not save localized names: %s", exc)


def fetch_chinese_name(appid: str, timeout: float = 6.0) -> str:
    """Localized name for one app, or an empty string."""
    if not appid:
        return ""
    url = ("https://store.steampowered.com/api/appdetails?appids="
           f"{appid}&l=schinese&filters=basic")
    try:
        payload = net.get_json(url, timeout=timeout, retries=1)
    except (net.NetworkError, ValueError) as exc:
        log.debug("name lookup failed for %s: %s", appid, exc)
        return ""
    entry = payload.get(str(appid)) if isinstance(payload, dict) else None
    if isinstance(entry, dict) and entry.get("success"):
        return str((entry.get("data") or {}).get("name") or "")
    return ""
