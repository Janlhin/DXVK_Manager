"""Load every QML component off screen and report what breaks.

``qml_smoke.py`` renders the whole window once. That proves the app
starts, but it cannot tell which page a broken binding belongs to, and it
never exercises the small components on their own.

This module loads each QML file as an independent component against the
*real* bridge and models, so a component that lost a dependency in a
refactor fails here instead of failing silently on screen. It is the
regression net that the QML split was postponed for (T37).

Using the real bridge rather than a stub matters: a stub has to be kept
in sync with every signal and slot by hand, and a stub that drifts turns
"property not found" into a false alarm. The real one cannot drift.

Hosting: a file whose root is an ``Item`` can be loaded directly, but a
root ``Dialog`` or ``Popup`` has no parent while it is a top-level object
and would fail on ``parent.height``. Such a file is loaded inside a
throw-away window instead. The probe wrapper is written next to the file
(it needs the same import directory), named with a double underscore so
the QML tree walk ignores it, and deleted afterwards.

Run standalone::

    python tests/qml_components.py

Needs PySide6 and a writable data directory; it is a local gate, not part
of the headless CI run (CI has no PySide6 installed).
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\WindowsFonts")
os.environ.setdefault(
    "DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-qml-components")
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QQuickStyle.setStyle("Basic")

FAILURES: list[str] = []

# The root type of a QML file: the first ``Type {`` on its own line.
ROOT_TYPE_RE = re.compile(r"^([A-Z][A-Za-z0-9_]*)\s*\{", re.MULTILINE)

# Types that are not Items and therefore need a window around them.
NON_ITEM_ROOTS = {"ApplicationWindow", "Window", "Dialog", "Popup", "Menu"}

# QML error shapes worth failing on. Anything that says "this object has
# no such property" or "this name does not exist" is a real wiring bug.
#
# "no such directory" and "unavailable" matter just as much: a QML file
# that imports a sibling with a path the engine cannot resolve still
# loads *something* - the page renders, minus the missing part - so the
# failure is otherwise invisible.
ERROR_MARKERS = (
    "referenceerror",
    "is not defined",
    "typeerror",
    "cannot read property",
    "cannot assign",
    "is not a function",
    "unable to assign",
    "cannot load",
    "no such directory",
    "unavailable",
    "is not a type",
    "duplicate",
    "invalid override",
)

PROBE_NAME = "__probe.qml"


def probe_wrapper(root_type: str) -> str:
    """A throw-away window that hosts a non-Item root."""
    return (
        "import QtQuick\n"
        "import QtQuick.Controls\n"
        "import QtQuick.Layouts\n"
        "ApplicationWindow {\n"
        "    width: 1200\n"
        "    height: 800\n"
        "    visible: true\n"
        f"    {root_type} {{ id: probeRoot }}\n"
        "}\n"
    )


def main() -> int:
    problems: list[str] = []

    def handler(mode, context, message):  # noqa: ANN001
        text = str(message)
        lowered = text.lower()
        if any(marker in lowered for marker in ERROR_MARKERS):
            problems.append(text)

    qInstallMessageHandler(handler)

    from dxvk_toolkit.ui.app_qml import QML_DIR
    from dxvk_toolkit.ui.bridge import Bridge

    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()
    bridge = Bridge()
    context = engine.rootContext()
    context.setContextProperty("bridge", bridge)
    context.setContextProperty("gameModel", bridge.model)
    context.setContextProperty("configModel", bridge.config)

    files = sorted(QML_DIR.rglob("*.qml"))
    print(f"loading {len(files)} QML components off screen:")
    for path in files:
        problems.clear()
        source = path
        cleanup: Path | None = None

        text = path.read_text(encoding="utf-8")
        root_match = ROOT_TYPE_RE.search(text)
        root_type = root_match.group(1) if root_match else ""
        if root_type in NON_ITEM_ROOTS and root_type not in {"ApplicationWindow", "Window"}:
            # Needs a parent: host it in a throw-away window.
            cleanup = path.parent / PROBE_NAME
            cleanup.write_text(probe_wrapper(root_type), encoding="utf-8")
            source = cleanup

        engine.load(QUrl.fromLocalFile(str(source)))
        # A few event turns: bindings settle over several frames, and a
        # broken one only reports once its value is first read.
        for _ in range(3):
            app.processEvents()
        roots = engine.rootObjects()
        ok = bool(roots) and not problems
        detail = ""
        if not ok:
            detail = problems[0].split("] ")[-1][:170] if problems else "no root object"
            FAILURES.append(f"{path.name}: {detail}")
        print(f"  [{'OK  ' if ok else 'FAIL'}] {path.name}"
              f"{(' - ' + detail) if detail else ''}")
        engine.clearComponentCache()
        if cleanup is not None and cleanup.exists():
            cleanup.unlink()

    bridge.shutdown()

    if FAILURES:
        print(f"\nresult: FAIL ({len(FAILURES)} problems)")
        for item in FAILURES:
            print(f"  - {item}")
        return 2

    print(f"\nresult: PASS ({len(files)} components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
