"""Where the standalone configurator keeps its state.

The full application stores its settings in ``settings.json`` next to the
installed DXVK versions. This tool has none of those, so it keeps its own
file in a directory of its own: sharing the file would make the two tools
overwrite each other's keys.

The shape of the file is the same as the application's (a flat JSON object),
because the presets and the option selections are the same kind of data.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

APP_SLUG = "DXVK-Configurator-Py"

DEFAULT_SETTINGS: dict[str, Any] = {
    # Documentation language: "zh" uses the bundled translation, "en" the raw
    # DXVK comments.
    "docs_language": "zh",
    # Interface language.
    "ui_lang": "zh",
    # Write the documentation above each option in the generated dxvk.conf.
    "conf_comments": True,
    # The reference dxvk.conf the option list is built from. Empty means the
    # bundled copy.
    "reference_conf": "",
    # The last opened .conf file.
    "last_file": "",
    "last_dir": "",
    # Selections of the open file, keyed by its absolute path.
    "selections": {},
    # Custom presets.
    "config_presets": {},
    # The mode of the option list ("simple" / "advanced" / "full").
    "config_mode": "simple",
    # The width of the preview pane.
    "config_preview_width": 0,
}

_LOCK = threading.RLock()


def _default_root() -> Path:
    """Where the settings live when no override is given.

    Same convention as the full application: on Windows the local app data
    folder, elsewhere the XDG data folder.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_SLUG
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_SLUG
    return Path.home() / ".local" / "share" / APP_SLUG


def data_root() -> Path:
    """Root of everything this tool writes."""
    override = os.environ.get("DXVK_CONFIGURATOR_HOME")
    root = Path(override).expanduser() if override else _default_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def settings_path() -> Path:
    return data_root() / "settings.json"


class Settings:
    """A small JSON-backed settings store."""

    def __init__(self) -> None:
        self._data = dict(DEFAULT_SETTINGS)
        path = settings_path()
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = {}
        if isinstance(loaded, dict):
            self._data.update(loaded)

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

    def as_dict(self) -> dict[str, Any]:
        with _LOCK:
            return dict(self._data)

    def flush(self) -> None:
        with _LOCK:
            path = settings_path()
            tmp = path.with_suffix(".json.tmp")
            try:
                tmp.write_text(
                    json.dumps(self._data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                os.replace(tmp, path)
            except OSError:
                pass


settings = Settings()
