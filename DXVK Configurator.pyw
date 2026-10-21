"""Windowed launcher for the standalone dxvk.conf configurator.

Double-click this file on Windows to start the configurator without a console
window. The script folder is sys.path[0], so the package imports without any
path surgery.

The file type is associated with the *system* Python launcher, which may not be
the interpreter that has PySide6 installed. To stay self-contained we re-launch
ourselves with the project's bundled virtualenv interpreter (also windowed) when
we detect we are not already running under it. A windowed program has no console,
so any hard failure is surfaced through a message box instead of being silently
swallowed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SELF = Path(__file__).resolve()
VENV_PYW = SELF.parent / ".venv" / "Scripts" / "pythonw.exe"


def _using_venv_pythonw() -> bool:
    try:
        return Path(sys.executable).resolve() == VENV_PYW.resolve()
    except OSError:
        return False


def _show_error(message: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0, message, "DXVK Configurator", 0x10  # MB_ICONERROR
        )
    except Exception:
        pass


if not _using_venv_pythonw():
    if VENV_PYW.exists():
        # Re-launch with the bundled virtualenv interpreter (also windowed).
        subprocess.Popen([str(VENV_PYW), str(SELF)])
        raise SystemExit(0)
    _show_error(
        "找不到项目的 Python 虚拟环境（.venv）。\n\n"
        "请先在本仓库目录运行：\n"
        "  python -m venv .venv\n"
        "  .venv\\Scripts\\pip install -r requirements.txt"
    )
    raise SystemExit(1)

from dxvk_toolkit.standalone import main  # noqa: E402 - must run after the re-exec check above

if __name__ == "__main__":
    raise SystemExit(main())
