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
from .detect import (  # noqa: F401 - re-exported for existing callers
    KNOWN_DLLS,
    describe_game,
    detect_arch,
    detect_direct3d,
    flush_detect_cache,
    guess_direct3d,
    scan_runtime_dlls,
)
from .paths import data_root
from .util import log

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
        """Rebuild a manually added game from the settings file.

        A missing ``install_dir`` used to fall through to ``Path("")`` - the
        process working directory - which then looked like a real game folder
        and could receive DXVK files. The entry is rejected at the boundary
        instead; callers skip it and log.
        """
        raw_dir = str(payload.get("install_dir") or "").strip()
        if not raw_dir:
            raise ValueError("manual game entry has no install_dir")
        install_dir = Path(raw_dir)
        return cls(
            appid=str(payload.get("appid") or "manual"),
            name=str(payload.get("name") or install_dir.name),
            install_dir=install_dir,
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

def _read_epic_manifest(path: Path) -> Game | None:
    """Parse one Epic ``.item`` install manifest into a Game (or skip it)."""
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


def _egl_data_root() -> Path | None:
    """Root of the Epic Games Launcher (EGL) v2 data folder.

    Modern launchers keep installed-game metadata under
    ``com.epicgames.eglv2``; the path is advertised in the registry, so we
    read it there first and fall back to the well-known default.
    """
    if os.name == "nt":
        try:
            import winreg  # noqa: WPS433
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Epic Games\EpicGamesLauncher"
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppDataPath")
                if value and Path(str(value)).is_dir():
                    return Path(str(value))
        except (OSError, ValueError, ImportError):
            pass
    default = Path(os.environ.get("LOCALAPPDATA", "")) / "com.epicgames.eglv2"
    return default if default.is_dir() else None


def _epic_catalog_titles(egl_root: Path) -> dict[str, str]:
    """Map an Epic catalog ``namespace`` to its display title.

    The launcher caches the store catalog locally; reusing it gives us the
    proper localized name (e.g. "Alan Wake Remastered") instead of the raw
    install-folder name.
    """
    cache = egl_root / "cache" / "prod" / "catalog-cache.json"
    titles: dict[str, str] = {}
    if not cache.is_file():
        return titles
    try:
        data = json.loads(cache.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return titles
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, dict):
        return titles
    for value in items.values():
        if not isinstance(value, dict):
            continue
        item = value.get("item")
        if not isinstance(item, dict):
            continue
        namespace = item.get("namespace")
        title = item.get("title")
        if namespace and title and str(namespace) not in titles:
            titles[str(namespace)] = str(title)
    return titles


def _epic_name_from_manifests(egl_root: Path, directory: str) -> str:
    """Find a display name for ``directory`` in any readable ``.item`` file."""
    key = os.path.normcase(os.path.abspath(directory))
    for sub in ("Manifests", os.path.join("import-scan", "v1-items")):
        search = egl_root / sub
        if not search.is_dir():
            continue
        for item in search.glob("*.item"):
            game = _read_epic_manifest(item)
            if game is None:
                continue
            if os.path.normcase(os.path.abspath(str(game.install_dir))) == key:
                return game.name
    return ""


def _epic_installations(egl_root: Path | None) -> list[Game]:
    """Installed Epic games from EGL v2's authoritative ``installations.jsonl``.

    Each line is a JSON record carrying ``dir`` (install location),
    ``namespace`` and ``complete``. The header line (and unrelated records)
    carry no ``dir`` and are skipped. Folders missing from disk are dropped;
    duplicates sharing a folder keep the fully-installed entry.
    """
    if egl_root is None:
        return []
    jsonl = egl_root / "installations.jsonl"
    if not jsonl.is_file():
        return []
    titles = _epic_catalog_titles(egl_root)
    best: dict[str, tuple[bool, Game]] = {}
    try:
        lines = jsonl.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if not isinstance(data, dict) or not data.get("dir"):
            continue  # header / non-install record
        directory = str(data["dir"]).strip()
        try:
            key = os.path.normcase(os.path.abspath(directory))
        except OSError:
            continue
        if not os.path.isdir(directory):
            continue
        namespace = str(data.get("namespace") or "").strip()
        name = titles.get(namespace) or _epic_name_from_manifests(egl_root, directory)
        if not name:
            name = Path(directory).name
        appid = namespace or Path(directory).name.lower()
        game = Game(appid=appid, name=name, install_dir=Path(directory), source="epic")
        complete = bool(data.get("complete"))
        existing = best.get(key)
        if existing is None or (complete and not existing[0]):
            best[key] = (complete, game)
    return [game for _, game in best.values()]


def _epic_legacy_manifests() -> list[Game]:
    """Fallback ``.item`` manifests for older / side-by-side EGL installs."""
    games: list[Game] = []
    seen: set[str] = set()
    directories: list[Path] = []
    program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    directories.append(program_data / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests")
    directories.append(program_data / "EpicGamesLauncher" / "Data" / "Manifests")
    egl_root = _egl_data_root()
    if egl_root is not None:
        directories.append(egl_root / "Manifests")
        directories.append(egl_root / "import-scan" / "v1-items")
    for directory in directories:
        if not directory.is_dir():
            continue
        for item in sorted(directory.glob("*.item")):
            game = _read_epic_manifest(item)
            if game is None or game.key in seen:
                continue
            seen.add(game.key)
            games.append(game)
    return games


def scan_epic_games(manifest_dir: str | os.PathLike[str] | None = None) -> list[Game]:
    """Epic Games Launcher titles.

    With ``manifest_dir`` supplied we scan that folder's ``.item`` manifests
    only (used by tests and for explicit paths). Otherwise we read EGL v2's
    authoritative ``installations.jsonl`` and merge in any legacy ``.item``
    manifests so older installs are still covered.
    """
    if manifest_dir is not None:
        directory = Path(manifest_dir)
        if not directory.is_dir():
            return []
        games: list[Game] = []
        seen: set[str] = set()
        for manifest in sorted(directory.glob("*.item")):
            game = _read_epic_manifest(manifest)
            if game is None or game.key in seen:
                continue
            seen.add(game.key)
            games.append(game)
        return games

    games = _epic_installations(_egl_data_root())
    seen = {game.key for game in games}
    for legacy in _epic_legacy_manifests():
        if legacy.key in seen:
            continue
        seen.add(legacy.key)
        games.append(legacy)
    games.sort(key=lambda g: g.name.lower())
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


def _wegame_apps_roots() -> list[Path]:
    """Locate every WeGame rail_apps library (e.g. D:\\WeGameApps\\rail_apps).

    Installed titles live under ``<library>\\rail_apps\\<Name>(<id>)``. The
    library root is chosen by the user at install time, so probe the common
    drive roots instead of trusting one hardcoded path.
    """
    roots: list[Path] = []
    seen: set[str] = set()
    for drive in ("C:/", "D:/", "E:/", "F:/"):
        for candidate in (Path(drive) / "WeGameApps" / "rail_apps", Path(drive) / "rail_apps"):
            try:
                exists = candidate.is_dir()
            except OSError:
                exists = False
            if exists:
                key = os.path.normcase(os.path.abspath(candidate))
                if key not in seen:
                    seen.add(key)
                    roots.append(candidate)
    return roots


def _wegame_display_name(game_dir: Path, bare_name: str) -> str:
    """Localized display name for a WeGame title.

    WeGame ships an uninstaller named ``<DisplayName>卸载.exe`` inside the game
    folder; that is the most reliable place to recover the user-visible (often
    Chinese) name. Fall back to the folder's bare name when absent.
    """
    matches: list[str] = []
    try:
        names = os.listdir(game_dir)
    except OSError:
        return bare_name
    for f in names:
        if f.endswith("卸载.exe"):
            cand = f[: -len("卸载.exe")].strip()
            if cand:
                matches.append(cand)
    if not matches:
        return bare_name
    for m in matches:
        if m == bare_name or bare_name.startswith(m) or m.startswith(bare_name):
            return m
    return min(matches, key=len)


_RAIL_FOLDER_RE = re.compile(r"^(?P<nm>.+?)\((?P<id>\d+)\)$")


def _rail_apps_game_id(install_dir: Path) -> str | None:
    """Return the ``<id>`` of the rail_apps ``<Name>(<id>)`` ancestor of a
    path, if it sits inside one. Used to merge registry records that point at a
    sub-folder (e.g. ``…\\无畏契约(2001715)\\live``) with the same game the
    disk scan already discovered from the parent folder."""
    try:
        cur = Path(os.path.abspath(install_dir))
    except OSError:
        return None
    for _ in range(8):
        parent = cur.parent
        if parent.name == "rail_apps":
            match = _RAIL_FOLDER_RE.match(cur.name)
            return match.group("id") if match else cur.name
        if parent == cur:
            break
        cur = parent
    return None


def _wegame_games_from_rail_apps(root: Path) -> list[Game]:
    """Every ``<Name>(<id>)`` folder under a rail_apps directory."""
    games: list[Game] = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return games
    for name in entries:
        folder = root / name
        try:
            if not folder.is_dir():
                continue
        except OSError:
            continue
        match = re.match(r"^(?P<nm>.+?)\((?P<id>\d+)\)$", name)
        if match:
            bare, appid = match.group("nm"), match.group("id")
        else:
            bare, appid = name, name
        display = _wegame_display_name(folder, bare)
        games.append(
            Game(appid=str(appid), name=display, install_dir=folder, source="wegame")
        )
    return games


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
    """WeGame / rail titles.

    The on-disk ``rail_apps`` library is the authoritative installed list and
    is scanned first; the per-app ``HKCU\\Software\\Tencent`` registry records
    are merged as a fallback for machines where the library folder cannot be
    located. Duplicates by install folder are dropped.
    """
    if os.name != "nt":
        return []
    import winreg  # noqa: WPS433

    games: list[Game] = []
    disk_ids: set[str] = set()
    for root in _wegame_apps_roots():
        for game in _wegame_games_from_rail_apps(root):
            games.append(game)
            game_id = _rail_apps_game_id(game.install_dir)
            if game_id:
                disk_ids.add(game_id)
    for game in _wegame_games_from_entries(
        _registry_subkey_values(winreg.HKEY_CURRENT_USER, r"Software\Tencent")
    ):
        # Skip registry records already covered by the disk scan (same rail
        # app id, e.g. valorant.live pointing at the game's \\live sub-folder).
        if _rail_apps_game_id(game.install_dir) in disk_ids:
            continue
        games.append(game)
    seen: set[str] = set()
    out: list[Game] = []
    for game in games:
        key = game.key
        if key in seen:
            continue
        seen.add(key)
        out.append(game)
    return out


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
