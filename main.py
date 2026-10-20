"""Launcher: python main.py  (or double-click the .pyw next to it).

The script's own folder is already sys.path[0] when Python runs a file, so no
path surgery is needed; the redundant insert was easy to get wrong when the
package layout changed.
"""

from __future__ import annotations

from dxvk_toolkit.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
