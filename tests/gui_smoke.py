"""Headless-ish GUI smoke test: build every tab, screenshot it, then exit.

Run:  python tests/gui_smoke.py [output_dir]
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-toolkit-gui-smoke"))

# Never disturb the desktop: hidden by default, capture only when asked.
VISIBLE = "--visible" in sys.argv
SHOTS = "--shots" in sys.argv

from dxvk_toolkit.gui.app import build_app  # noqa: E402
from dxvk_toolkit.util import setup_logging  # noqa: E402


def pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.05)


def screenshot(app, target: Path) -> str:
    """Disabled on purpose.

    This script used to sample the screen with a screen-grab call. That is
    exactly how it once captured a window it had no business looking at, so the
    capability is gone: no code path here can read the screen any more.
    """
    return "screen capture is disabled in this build"


def main() -> int:
    setup_logging()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "dxvk-gui-shots"
    app = build_app()
    if not VISIBLE:
        app.withdraw()          # build and drive the UI without showing it
    app.update()
    pump(app, 12.0)  # let the Steam scan and the detection pass land

    results = []
    for key in ("games", "versions", "gplasync", "config", "settings"):
        app.show_tab(key)
        pump(app, 1.5 if key != "config" else 2.5)
        results.append((key, screenshot(app, out / f"{key}.png")))
        if key == "config":
            tab = app.tab("config")
            results.append(("config-options", f"{len(tab.rows)} rows rendered, model={tab.model.option_count if tab.model else 0}"))
            tab.search.set("frame")
            pump(app, 1.2)
            tab.advanced_var.set(True)
            tab._toggle_advanced()
            pump(app, 2.5)
            results.append(("config-search", f"{len(tab.rows)} rows after search+advanced"))
            results.append(("config-preview", tab.current_text().splitlines()[0] if tab.current_text() else "empty"))
            results.append(("config-preview-lines", str(len(tab.current_text().splitlines()))))

    # Modal dialogs are built and destroyed without entering their own loop.
    from dxvk_toolkit.gui.tab_config import PickGameDialog
    from dxvk_toolkit.gui.tab_games import ApplyDxvkDialog

    games_tab = app.tab("games")
    rows = games_tab.tree.tree.get_children()
    if rows:
        games_tab.tree.tree.selection_set(rows[0])
        app.update()
        d3d, arch = games_tab._detected(games_tab.games[0])
        dialog = ApplyDxvkDialog(app, games_tab.games[0], d3d_hint=d3d, arch_hint=arch)
        pump(app, 0.8)
        results.append(("apply-dialog", screenshot(app, out / "apply-dialog.png")))
        results.append(("apply-dialog-values", f"{len(dialog.values)} cached versions listed"))
        dialog.close()

    picker = PickGameDialog(app, "")
    pump(app, 0.6)
    results.append(("pick-dialog", screenshot(app, out / "pick-dialog.png")))
    results.append(("pick-dialog-entries", str(picker.listbox.size())))
    picker.close()

    games_tab._render()
    results.append(("detection-done", f"{sum(1 for g in games_tab.games if games_tab.detection.get(g.key, {}).get('direct3d') not in (None, '', 'Unknown'))} identified"))

    app.runner.stop()
    app.destroy()
    for name, message in results:
        print(f"{name:18s} {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())