"""Application paths, settings and the per-game ledger."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

APP_SLUG = "DXVK-Version-Manager-Py"

DEFAULT_SETTINGS: dict[str, Any] = {
    # "auto" tries a direct connection first and then the local proxy found in
    # the Windows settings; "direct" never uses a proxy; "custom" always uses
    # the proxy_url below.
    # When true no request leaves the machine at all (SPEC section 3).
    "offline_mode": False,
    "proxy_mode": "auto",
    "proxy_url": "",
    # Reference dxvk.conf used to build the option list. Empty means "pick
    # automatically" (bundled copy first, then the newest downloaded release).
    "reference_conf": "",
    "show_advanced": False,
    # Documentation language: "zh" uses the bundled translation, "en" the raw
    # DXVK comments.
    "docs_language": "zh",
    # Write the documentation above each option in the generated dxvk.conf
    # (the reference file does the same, and the original configurator did too).
    "conf_comments": True,
    "keep_archive": False,
    # "auto" tries GitHub first and then mirrors, "official" never uses a
    # mirror, "mirror:<prefix>" pins one.
    "download_source": "auto",
    "steam_extra_libraries": [],
    "manual_games": [],
    "window_geometry": "",
    "last_export_dir": "",
}

_LOCK = threading.RLock()


def _default_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_SLUG
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_SLUG
    return Path.home() / ".local" / "share" / APP_SLUG


def data_root() -> Path:
    """Root of everything the application writes."""
    override = os.environ.get("DXVK_MANAGER_HOME")
    root = Path(override).expanduser() if override else _default_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def cache_dir(kind: str = "dxvk") -> Path:
    """Cache directory for extracted DXVK packages.

    kind is "dxvk" for upstream DXVK and "gplasync" for the async fork.
    """
    name = "dxvk-gplasync-cache" if kind == "gplasync" else "dxvk-cache"
    path = data_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def archives_dir() -> Path:
    path = data_root() / "archives"
    path.mkdir(parents=True, exist_ok=True)
    return path


def meta_dir() -> Path:
    path = data_root() / "games-meta" / "metadata"
    path.mkdir(parents=True, exist_ok=True)
    return path


def covers_dir() -> Path:
    path = data_root() / "games-meta" / "covers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = data_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_root() / "settings.json"


def ledger_path() -> Path:
    return data_root() / "games.json"


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            return loaded
    except (FileNotFoundError, OSError, ValueError):
        pass
    return dict(fallback)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


class Settings:
    """Small JSON-backed settings store."""

    def __init__(self) -> None:
        self._data = dict(DEFAULT_SETTINGS)
        self._data.update(_read_json(settings_path(), {}))

    def get(self, key: str, default: Any = None) -> Any:
        with _LOCK:
            if key in self._data:
                return self._data[key]
            if default is not None:
                return default
            return DEFAULT_SETTINGS.get(key)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        with _LOCK:
            self._data[key] = value
            if save:
                self.flush()

    def update(self, values: dict[str, Any]) -> None:
        with _LOCK:
            self._data.update(values)
            self.flush()

    def as_dict(self) -> dict[str, Any]:
        with _LOCK:
            return dict(self._data)

    def flush(self) -> None:
        with _LOCK:
            _write_json(settings_path(), self._data)


settings = Settings()


class Ledger:
    """Remembers which games were patched, with what version, and when.

    The game directory itself stays the source of truth (backup files and DXVK
    signatures are read from disk); the ledger only adds provenance.
    """

    def __init__(self) -> None:
        payload = _read_json(ledger_path(), {"version": 1, "games": {}})
        games = payload.get("games")
        self._games: dict[str, dict[str, Any]] = games if isinstance(games, dict) else {}

    @staticmethod
    def key_for(game_dir: str | os.PathLike[str]) -> str:
        try:
            return os.path.normcase(os.path.abspath(str(game_dir)))
        except OSError:
            return str(game_dir).lower()

    def get(self, game_dir: str | os.PathLike[str]) -> dict[str, Any]:
        with _LOCK:
            return dict(self._games.get(self.key_for(game_dir), {}))

    def record(self, game_dir: str | os.PathLike[str], **fields: Any) -> dict[str, Any]:
        with _LOCK:
            key = self.key_for(game_dir)
            entry = dict(self._games.get(key, {}))
            entry.update(fields)
            entry["install_dir"] = os.path.abspath(str(game_dir))
            entry["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._games[key] = entry
            _write_json(ledger_path(), {"version": 1, "games": self._games})
            return dict(entry)

    def forget(self, game_dir: str | os.PathLike[str]) -> None:
        with _LOCK:
            self._games.pop(self.key_for(game_dir), None)
            _write_json(ledger_path(), {"version": 1, "games": self._games})

    def all(self) -> dict[str, dict[str, Any]]:
        with _LOCK:
            return {k: dict(v) for k, v in self._games.items()}

    def prune_missing(self) -> list[str]:
        """Drop records whose game folder no longer exists; returns their paths.

        Uninstalled games would otherwise keep their "managed/adopted" entry
        forever, cluttering the ledger with directories that can never be
        upgraded or restored again.
        """
        with _LOCK:
            dropped: list[str] = []
            for key in list(self._games):
                install_dir = str(self._games[key].get("install_dir") or key)
                if not os.path.isdir(install_dir):
                    self._games.pop(key, None)
                    dropped.append(install_dir)
            if dropped:
                _write_json(ledger_path(), {"version": 1, "games": self._games})
            return dropped


ledger = Ledger()


def bundle_dir() -> Path:
    """Directory shipped with the application (assets, README)."""
    here = Path(__file__).resolve().parent
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", here))
    return here.parent


def asset_path(name: str) -> Path:
    return bundle_dir() / "assets" / name
