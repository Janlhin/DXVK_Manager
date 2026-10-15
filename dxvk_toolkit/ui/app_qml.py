"""Application entry point for the QML interface."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTranslator, QUrl
from PySide6.QtGui import QColor, QPalette
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from ..paths import asset_path, settings
from ..util import log, setup_logging
from .bridge import Bridge

QML_DIR = Path(__file__).resolve().parent / "qml"


def _dark_palette() -> QPalette:
    """A dark application palette.

    Controls that the QML side does not style itself - tool tips, combo box
    popups, menus - take their colours from here. Without it the default light
    palette produced glaring white tool tips in the middle of a dark window.
    """
    palette = QPalette()
    pairs = {
        QPalette.Window: "#141619",
        QPalette.WindowText: "#e7e9ec",
        QPalette.Base: "#1b1e23",
        QPalette.AlternateBase: "#20242b",
        QPalette.Text: "#e7e9ec",
        QPalette.Button: "#20242b",
        QPalette.ButtonText: "#e7e9ec",
        QPalette.BrightText: "#e5686a",
        QPalette.ToolTipBase: "#20242b",
        QPalette.ToolTipText: "#e7e9ec",
        QPalette.Highlight: "#33549f",
        QPalette.HighlightedText: "#e6ecfb",
        QPalette.PlaceholderText: "#6f7885",
    }
    for role, value in pairs.items():
        palette.setColor(role, QColor(value))
    return palette


# The currently installed interface translator, kept so it can be swapped at
# runtime when the user changes ui_lang (§28 hot-swap — no restart needed).
_current_translator: QTranslator | None = None
# The QML engine, set once in run(); retranslate() after a swap so qsTr()
# bindings re-evaluate (installing/removing a translator alone is not enough).
_engine: QQmlApplicationEngine | None = None


def set_language(lang: str) -> None:
    """Install or remove the interface catalogue for ``lang`` (§28).

    Chinese is the source language, so zh needs no catalogue; English loads
    assets/i18n/app_en.qm, which covers both the QML qsTr() strings and the
    Python tr()/QCoreApplication.translate() ones.

    After the swap, ``engine.retranslate()`` re-evaluates every qsTr() binding
    so the static UI text switches without a restart (simply installing the
    translator does not refresh already-loaded QML). Model strings resolved in
    Python are refreshed separately by ``GameListModel.retranslate()``.
    """
    global _current_translator
    app = QApplication.instance()
    if app is None:
        return
    if _current_translator is not None:
        app.removeTranslator(_current_translator)
        _current_translator = None
    if str(lang or "zh") != "en":
        if _engine is not None:
            _engine.retranslate()
        return
    qm = asset_path("i18n/app_en.qm")
    if not qm.is_file():
        log.warning("ui_lang=en but catalogue missing: %s", qm)
        if _engine is not None:
            _engine.retranslate()
        return
    translator = QTranslator(app)
    if translator.load(str(qm)):
        app.installTranslator(translator)
        _current_translator = translator
    else:
        log.warning("could not load translation catalogue: %s", qm)
    if _engine is not None:
        _engine.retranslate()


def run(argv: list[str] | None = None) -> int:
    setup_logging()
    # The native Windows style refuses custom backgrounds, so the cross
    # platform "Basic" style is selected through the API: an environment
    # variable would be read too late once Qt has been imported.
    QQuickStyle.setStyle("Basic")

    app = QApplication(argv if argv is not None else sys.argv)
    set_language(str(settings.get("ui_lang") or "zh"))
    app.setPalette(_dark_palette())
    app.setApplicationName("DXVK Version Manager")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("dxvk-toolkit")

    engine = QQmlApplicationEngine()
    global _engine
    _engine = engine
    bridge = Bridge()
    context = engine.rootContext()
    context.setContextProperty("bridge", bridge)
    context.setContextProperty("gameModel", bridge.model)
    context.setContextProperty("configModel", bridge.config)
    engine.addImportPath(str(QML_DIR))

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "main.qml")))
    if not engine.rootObjects():
        log.error("QML failed to load from %s", QML_DIR)
        return 1
    try:
        return app.exec()
    finally:
        bridge.shutdown()


__all__ = ["run", "QML_DIR"]
