"""Render every page off screen, with real fonts, so the layout can be judged.

Nothing is shown on the desktop: the offscreen platform never creates a visible
window, and grabWindow() only ever reads our own scene.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QObject, QUrl  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QQuickStyle.setStyle("Basic")

WINDOWS_FONTS = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\consola.ttf",
)


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "dxvk-ui"
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    for path in WINDOWS_FONTS:            # the offscreen backend has no fonts
        if os.path.isfile(path):
            QFontDatabase.addApplicationFont(path)

    from dxvk_toolkit.ui.app_qml import QML_DIR, _dark_palette
    from dxvk_toolkit.ui.bridge import Bridge

    app.setPalette(_dark_palette())
    engine = QQmlApplicationEngine()
    bridge = Bridge()
    context = engine.rootContext()
    context.setContextProperty("bridge", bridge)
    context.setContextProperty("gameModel", bridge.model)
    context.setContextProperty("configModel", bridge.config)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "main.qml")))
    if not engine.rootObjects():
        print("FAIL: QML did not load")
        return 1
    window = engine.rootObjects()[0]
    window.setProperty("width", 1600)
    window.setProperty("height", 900)

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    pump(4)
    deadline = time.time() + 30
    while time.time() < deadline and bridge.model.rowCount() == 0:
        pump(0.2)
    pump(6)                                # let detection and covers settle

    # Fill the details panel with a sample so it shows up in the capture.
    detail = window.findChild(QObject, "gameDetails")
    if detail is not None:
        detail.setProperty("gameKey", "sample")
        detail.setProperty("name", "Call of Duty: Modern Warfare")
        detail.setProperty("path", r"D:\SteamLibrary\steamapps\common\Call of Duty Modern Warfare")
        detail.setProperty("platform", "Steam")
        detail.setProperty("direct3d", "Direct3D 12")
        detail.setProperty("arch", "x64")
        detail.setProperty("statusText", "未安装")
        detail.setProperty("statusKind", "muted")
        pump(1.0)

    for index, name in ((0, "games-grid"), (1, "versions"), (2, "config"), (3, "settings")):
        window.setProperty("currentPage", index)
        pump(1.5)
        window.grabWindow()
        pump(0.8)
        target = out_dir / f"{name}.png"
        window.grabWindow().save(str(target))
        print(f"{name:<12} -> {target}")

    # The config preview dialog is new code and worth looking at.
    from PySide6.QtCore import QMetaObject
    dialog = window.findChild(QObject, "previewDialog")
    if dialog is not None:
        window.setProperty("currentPage", 2)
        pump(1.0)
        QMetaObject.invokeMethod(dialog, "open")
        pump(1.5)
        target = out_dir / "config-preview.png"
        window.grabWindow().save(str(target))
        print(f"{'config-preview':<12} -> {target}")
        QMetaObject.invokeMethod(dialog, "close")
        pump(0.5)

    # The list variant of the games page is a separate view.
    grid = window.findChild(QObject, "gameGrid")
    if grid is not None:
        window.setProperty("currentPage", 0)
        grid.parent().setProperty("viewMode", "list")
        pump(2.0)
        window.grabWindow()
        pump(0.8)
        target = out_dir / "games-list.png"
        window.grabWindow().save(str(target))
        print(f"{'games-list':<12} -> {target}")

    bridge.shutdown()
    print("rows:", bridge.model.rowCount(), "| options:", bridge.config.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
