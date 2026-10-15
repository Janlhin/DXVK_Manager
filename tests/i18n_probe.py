"""Offscreen probe for the English interface catalogue (T15, §29).

Sets ui_lang=en in memory only (save=False), installs the translator exactly
like the real entry point does, spot-checks catalogue entries, then renders
the pages whose widgets carry translated strings. Nothing is persisted, so
the user's settings.json keeps its current language.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QObject, QTranslator, QUrl  # noqa: E402
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

# (context, source, expected English) — straight from assets/i18n/app_en.ts.
SPOT_CHECKS = (
    ("GamesPage", "名称", "Name"),
    ("GamesPage", "平台", "Platform"),
    ("ConfigPage", "带注释", "Comments"),
    ("SettingsPage", "界面语言", "Interface language"),
    ("Bridge", "正在扫描游戏库…", "Scanning the game library…"),
    ("GameListModel", "未安装", "Not installed"),
    # Platform labels reach the UI through _tr() with a variable source, so
    # lupdate never sees them - the catalogue entry is the only guard (T23).
    ("GameListModel", "米哈游", "miHoYo"),
    ("GameListModel", "手动添加", "Manual"),
    ("GameListModel", "全部", "All"),
)


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build") / "i18n-render"
    out_dir.mkdir(parents=True, exist_ok=True)

    from dxvk_toolkit.paths import asset_path, settings

    settings.set("ui_lang", "en", save=False)  # memory only — nothing persisted

    app = QApplication(sys.argv)
    for path in WINDOWS_FONTS:
        if os.path.isfile(path):
            QFontDatabase.addApplicationFont(path)

    from dxvk_toolkit.ui.app_qml import QML_DIR, _dark_palette, _install_translator
    from dxvk_toolkit.ui.bridge import Bridge

    _install_translator(app)
    app.setPalette(_dark_palette())

    # Catalogue spot checks with a standalone translator (independent of the
    # installed one, so this also proves the .qm file itself is loadable).
    probe = QTranslator(app)
    qm = asset_path("i18n/app_en.qm")
    if not probe.load(str(qm)):
        print(f"FAIL: cannot load catalogue {qm}")
        return 1
    failures = 0
    for ctx, source, expected in SPOT_CHECKS:
        got = probe.translate(ctx, source)
        ok = got == expected
        failures += 0 if ok else 1
        print(f"{'ok ' if ok else 'BAD'} {ctx:<13} {source[:18]:<20} -> {got!r}")

    # Python-side end to end: QObject.tr() must route through the installed
    # translator at runtime, not just be present in the catalogue.
    engine = QQmlApplicationEngine()
    bridge = Bridge()
    via_tr = bridge.tr("正在扫描游戏库…")
    ok = via_tr == "Scanning the game library…"
    failures += 0 if ok else 1
    print(f"{'ok ' if ok else 'BAD'} Bridge.tr() live -> {via_tr!r}")

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
    grid_page = window.findChild(QObject, "gamesPage")
    if grid_page is not None:
        grid_page.setProperty("viewMode", "list")
    pump(0.6)
    deadline = time.time() + 30
    while time.time() < deadline and bridge.model.rowCount() == 0:
        pump(0.2)
    pump(4)

    # Settings page last-run combo state can point anywhere; park it on the
    # language card by scrolling top, then capture.
    for index, name in ((3, "en-settings"), (2, "en-config"), (0, "en-games-list")):
        window.setProperty("currentPage", index)
        pump(1.5)
        window.grabWindow()
        pump(0.8)
        target = out_dir / f"{name}.png"
        window.grabWindow().save(str(target))
        print(f"{name:<14} -> {target}")

    # Versions page chrome (buttons/labels); rows arrive from the network and
    # are not needed to judge the translated chrome.
    window.setProperty("currentPage", 1)
    pump(2.0)
    window.grabWindow()
    pump(0.8)
    target = out_dir / "en-versions.png"
    window.grabWindow().save(str(target))
    print(f"{'en-versions':<14} -> {target}")

    bridge.shutdown()
    print("failures:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
