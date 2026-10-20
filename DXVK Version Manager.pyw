"""Windowed launcher for Windows: double-click to start without a console.

The script folder is sys.path[0], so the package imports without the previous
sys.path insert.
"""

from __future__ import annotations

from dxvk_toolkit.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main([]))
