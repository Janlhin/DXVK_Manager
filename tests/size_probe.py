"""Render the settings page at the user's real window size for defect replay."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QUrl  # noqa: E402
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
    width = int(sys.argv[1]) if len(sys.argv) > 1 else 1093
    height = int(sys.argv[2]) if len(sys.argv) > 2 else 679
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("build") / "narrow-settings.png"
    page = int(sys.argv[4]) if len(sys.argv) > 4 else 3

    app = QApplication(sys.argv)
    for path in WINDOWS_FONTS:
        if os.path.isfile(path):
            QFontDatabase.addApplicationFont(path)

    from dxvk_toolkit.ui.app_qml import QML_DIR, _dark_palette
    from dxvk_toolkit.ui.bridge import Bridge

    app.setPalette(_dark_palette())
    engine = QQmlApplicationEngine()
    bridge = Bridge()
    ctx = engine.rootContext()
    ctx.setContextProperty("bridge", bridge)
    ctx.setContextProperty("gameModel", bridge.model)
    ctx.setContextProperty("configModel", bridge.config)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "main.qml")))
    if not engine.rootObjects():
        print("FAIL: QML did not load")
        return 1
    window = engine.rootObjects()[0]
    window.setProperty("width", width)
    window.setProperty("height", height)

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    pump(3)
    window.setProperty("currentPage", page)
    pump(2.0)
    window.grabWindow()
    pump(0.6)
    out.parent.mkdir(parents=True, exist_ok=True)
    window.grabWindow().save(str(out))
    print(f"{width}x{height} -> {out}")
    bridge.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
