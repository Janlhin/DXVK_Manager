"""Windowed launcher for the standalone dxvk.conf configurator.

Double-click this file on Windows to start the configurator without a console
window. The script folder is sys.path[0], so the package imports without any
path surgery.
"""

from __future__ import annotations

from dxvk_toolkit.standalone import main

if __name__ == "__main__":
    raise SystemExit(main())
