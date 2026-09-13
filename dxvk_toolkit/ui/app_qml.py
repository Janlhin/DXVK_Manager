"""Application entry point for the QML interface."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QPalette
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

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


def run(argv: list[str] | None = None) -> int:
    setup_logging()
    # The native Windows style refuses custom backgrounds, so the cross
    # platform "Basic" style is selected through the API: an environment
    # variable would be read too late once Qt has been imported.
    QQuickStyle.setStyle("Basic")

    app = QApplication(argv if argv is not None else sys.argv)
    app.setPalette(_dark_palette())
    app.setApplicationName("DXVK Version Manager")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("dxvk-toolkit")

    engine = QQmlApplicationEngine()
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
