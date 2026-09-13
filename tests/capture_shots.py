"""Capture the real window (only our window) for review."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-toolkit-shot"))

# --- safety first -----------------------------------------------------------
# These scripts must never disturb the desktop they run on. By default the
# window stays withdrawn, nothing steals focus and no screen capture happens.
# Pass --visible to show the window, --shots to also capture it (only ever the
# window itself, placed at the top-left so no other window is ever sampled).
VISIBLE = "--visible" in sys.argv
SHOTS = "--shots" in sys.argv

from dxvk_toolkit.gui.app import build_app  # noqa: E402


def pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.03)


def capture(app, target: Path) -> str:
    """Disabled on purpose - see the note in gui_smoke.py.

    Keeping screen capture around, even behind a flag, means it can be turned
    on by accident. It is removed instead.
    """
    return "screen capture is disabled in this build"


def main() -> int:
    app = build_app()
    app.geometry("1500x950")
    if not VISIBLE:
        app.withdraw()          # drive the UI without ever showing it
    app.update()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "shots2"
    app.tab("games")
    app.show_tab("games")
    pump(app, 20)          # scan + detection + covers
    print("grid:", capture(app, out / "grid.png"),
          "| specs:", len(app._tabs["games"].grid_view.specs))
    pump(app, 6)
    print("grid2:", capture(app, out / "grid-settled.png"))
    app._tabs["games"]._set_view("list")
    pump(app, 1.5)
    print("list:", capture(app, out / "list.png"))
    app._tabs["games"]._set_view("grid")
    app.show_tab("config")
    pump(app, 2.5)
    print("config:", capture(app, out / "config.png"))
    loader = getattr(app._tabs.get("games"), "loader", None)
    if loader:
        loader.shutdown()
    app.runner.stop()
    app.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())