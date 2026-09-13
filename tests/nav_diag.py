"""Simulate real navigation clicks and record every Tk callback error."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-toolkit-diag"))

from dxvk_toolkit.gui.app import build_app  # noqa: E402

ERRORS: list[str] = []


def main() -> int:
    app = build_app()

    def report(exc_type, exc_value, exc_tb):  # noqa: ANN001
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        ERRORS.append(text)
        print("!!! Tk callback error:\n" + text)

    app.report_callback_exception = report
    app.geometry("1400x900")
    app.update()
    pump(app, 1.0)

    print("tabs registered at startup:", sorted(app._tabs.keys()))
    print("lazy factories:", sorted(app._factories.keys()))

    for key, button in app._nav_buttons.items():
        before = {k: (v.winfo_ismapped() if v.winfo_exists() else None) for k, v in app._tabs.items()}
        try:
            button.invoke()
        except Exception as exc:  # noqa: BLE001
            print(f"{key:9s} invoke RAISED {type(exc).__name__}: {exc}")
            continue
        pump(app, 0.8)
        frame = app._tabs.get(key)
        mapped = bool(frame is not None and frame.winfo_exists() and frame.winfo_ismapped())
        visible = [k for k, f in app._tabs.items() if f.winfo_exists() and f.winfo_ismapped()]
        print(f"{key:9s} registered={key in app._tabs} mapped={mapped} visible_pages={visible} "
              f"current={app._current}")
        if before and not mapped:
            print(f"          before: {before}")

    print("errors captured:", len(ERRORS))
    app.destroy()
    return 0


def pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.03)


if __name__ == "__main__":
    raise SystemExit(main())
