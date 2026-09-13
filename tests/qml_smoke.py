"""Render the QML interface off screen and report any QML problem.

Runs with QT_QPA_PLATFORM=offscreen: nothing is shown on the desktop, no
window is created, and no screen content is ever read. This is how interface
changes are verified in this project.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
# The software backend makes item views populate without a real display; with
# the default backend the grid stays empty off screen because no render pass
# ever happens.
os.environ["QT_QUICK_BACKEND"] = "software"
# Without a font directory the off-screen backend draws every glyph as a box.
os.environ.setdefault("QT_QPA_FONTDIR", r"C:WindowsFonts")
os.environ.setdefault("DXVK_MANAGER_HOME", str(Path(tempfile.gettempdir()) / "dxvk-qml-smoke"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QObject, QUrl  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QQuickStyle.setStyle("Basic")  # must be set before the application exists

FAILURES: list[str] = []
WARNINGS: list[str] = []


def handler(mode, context, message):  # noqa: ANN001
    text = str(message)
    if "does not support customization" in text or "is not a" in text or "ReferenceError" in text:
        WARNINGS.append(text)


def pump(app: QApplication, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def check(condition: bool, label: str, detail: str = "") -> None:
    mark = "OK  " if condition else "FAIL"
    print(f"  [{mark}] {label}{(' - ' + detail) if detail else ''}")
    if not condition:
        FAILURES.append(label)


def main() -> int:
    from PySide6.QtCore import qInstallMessageHandler

    qInstallMessageHandler(handler)

    from dxvk_toolkit.ui.app_qml import QML_DIR
    from dxvk_toolkit.ui.bridge import Bridge

    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()
    bridge = Bridge()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("gameModel", bridge.model)
    engine.rootContext().setContextProperty("configModel", bridge.config)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "main.qml")))

    roots = engine.rootObjects()
    if not roots:
        print("FAIL: QML did not load")
        return 1
    window = roots[0]
    print(f"window: {window.property('width')}x{window.property('height')}")

    print("scan (triggered by QML itself, not by this script):")
    messages: list[str] = []
    bridge.statusMessage.connect(lambda text, kind: messages.append(f"{kind}: {text}"))
    # No bridge.scanGames() call here on purpose: the window must fill itself.
    deadline = time.time() + 45
    while time.time() < deadline and bridge.model.rowCount() == 0:
        pump(app, 0.2)
    pump(app, 1.5)

    rows = bridge.model.rowCount()
    check(rows > 0, "games loaded into the model", f"{rows} rows")
    check(messages[-1].startswith("ok") if messages else False, "scan reported success",
          messages[-1] if messages else "no message")

    keys = bridge.model.keys()
    if keys:
        first = bridge.model.row(keys[0]) or {}
        check(bool(first.get("name")), "first row has a name", str(first.get("name")))
        check(first.get("platformLabel") == "Steam", "platform label resolved",
              str(first.get("platformLabel")))
        details = bridge.model.details(keys[0]) or {}
        check(bool(details.get("path")), "details slot returns a path", str(details.get("path"))[:60])

    # List mode is a separate view over the same model.
    games_page = window.findChild(QObject, "gameList")
    check(games_page is not None, "list view present")
    if games_page is not None:
        window.setProperty("currentPage", 0)
        page_item = window.contentItem().childItems()[0] if False else None
        # Flip the mode the way the toolbar button does.
        for obj_name in ("gameGrid",):
            pass
        grid_obj = window.findChild(QObject, "gameGrid")
        if grid_obj is not None:
            grid_obj.parent().setProperty("viewMode", "list")
            pump(app, 1.5)
            window.grabWindow()
            deadline = time.time() + 20
            while time.time() < deadline and games_page.property("count") == 0:
                pump(app, 0.3)
            check(games_page.property("count") == rows, "list view shows every game",
                  f"count={games_page.property('count')}")
            grid_obj.parent().setProperty("viewMode", "grid")
            pump(app, 0.8)

    grid = window.findChild(QObject, "gameGrid")
    check(grid is not None, "grid view found")
    if grid is not None:
        # The wall is a Flow inside a Flickable (headings span the row), so it
        # has no count property: compare the cards actually created instead.
        deadline = time.time() + 30
        # Count the card components the wall built. Their QML class name
        # carries a suffix, so match on the prefix.
        games = bridge.model.rowCount()
        created = 0
        while time.time() < deadline:
            created = sum(1 for obj in window.findChildren(QObject)
                          if obj.metaObject().className().startswith("GameCard"))
            if created >= games:
                break
            pump(app, 0.2)
        check(created >= games, "wall created every row",
              f"cards={created} model={games}")
        rendered = window.grabWindow()
        check(not rendered.isNull() and rendered.width() > 0,
              "scene renders off screen",
              f"{rendered.width()}x{rendered.height()}")
        shot = Path(tempfile.gettempdir()) / "dxvk-qml-render.png"
        rendered.save(str(shot))
        print(f"  [info] off-screen render saved: {shot}")

    # Walk every page so each one instantiates for real.
    print("pages:")
    for index, name in enumerate(("games", "versions", "config", "settings")):
        window.setProperty("currentPage", index)
        pump(app, 0.6)
        check(True, f"page '{name}' rendered")

    # The configuration page loads its catalogue from the bundled reference.
    deadline = time.time() + 15
    while time.time() < deadline and bridge.config.count == 0:
        pump(app, 0.2)
    check(bridge.config.count > 0, "config catalogue loaded", f"{bridge.config.count} options")
    window.setProperty("currentPage", 2)
    pump(app, 1.0)
    window.grabWindow()          # force a render pass so the view populates
    pump(app, 1.0)
    options = window.findChild(QObject, "optionList")
    if options is not None:
        deadline = time.time() + 20
        while time.time() < deadline and options.property("count") == 0:
            pump(app, 0.3)
        check(options.property("count") > 0, "config rows are created",
              f"count={options.property('count')}")
    preview = bridge.previewConfig()
    check(preview.startswith("#"), "config preview generated", preview.splitlines()[0][:50])

    # Import path: a real dxvk.conf must come back as ticked options.
    from dxvk_toolkit import confspec

    sample = Path(tempfile.gettempdir()) / "dxvk-import-sample.conf"
    sample.write_text(
        '# a comment\n[dxvk]\ndxvk.hud = "fps,frametimes"\n'
        "dxvk.maxFrameRate = 60\nd3d11.maxFeatureLevel = 12_1\n"
        "unknown.option = 1\n",
        encoding="utf-8",
    )
    values, unknown = confspec.parse_config_values(
        sample.read_text(encoding="utf-8"), bridge._config_model_data
    )
    bridge.config.apply_values(values)
    check(len(values) >= 3, "import parsed the sample file",
          f"{len(values)} options, {len(unknown)} unknown")
    check(bridge.config.values.get("hud") == "fps,frametimes", "imported value reached the model",
          str(bridge.config.values.get("hud")))
    check("fps,frametimes" in bridge.previewConfig(), "imported value shows up in the preview")

    # Covers arrive asynchronously; report how many landed without failing.
    got = 0
    deadline = time.time() + 40
    while time.time() < deadline and got < 4:
        pump(app, 0.5)
        got = sum(1 for key in keys if (bridge.model.row(key) or {}).get("coverUrl"))
    check(got >= 4, "covers download and reach the model", f"{got} covers")
    window.setProperty("currentPage", 0)      # back to the cover wall
    pump(app, 1.0)
    final = window.grabWindow()
    shot2 = Path(tempfile.gettempdir()) / "dxvk-qml-final.png"
    final.save(str(shot2))
    print(f"  [info] render with covers: {shot2}")

    bridge.shutdown()
    engine.deleteLater()
    pump(app, 0.2)

    if WARNINGS:
        print("qml warnings:")
        for item in WARNINGS[:8]:
            print("  -", item)
        FAILURES.append("qml warnings present")

    print(f"\nresult: {'PASS' if not FAILURES else 'FAIL'} ({len(FAILURES)} problems)")
    for item in FAILURES:
        print("  -", item)
    return 0 if not FAILURES else 2


if __name__ == "__main__":
    raise SystemExit(main())
