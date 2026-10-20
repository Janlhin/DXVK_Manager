"""Where the standalone configurator finds its bundled files.

The full application resolves its assets through
:mod:`dxvk_toolkit.paths`, but that module also creates the application's
data directory and reads its settings.json at import time. The standalone
configurator must not do either - it has its own store - so it resolves the
assets itself.

Two layouts are supported:

* running from the source tree: ``<repo>/assets``
* running from a frozen build (PyInstaller): ``<bundle>/assets``
"""

from __future__ import annotations

import sys
from pathlib import Path


def bundle_dir() -> Path:
    """Root of everything that ships with the application."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return Path(__file__).resolve().parents[2]


def asset_path(name: str) -> Path:
    """Path of one bundled file, e.g. ``asset_path("dxvk.conf")``."""
    return bundle_dir() / "assets" / name


__all__ = ["asset_path", "bundle_dir"]
