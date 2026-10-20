"""The dark application palette.

Controls that the QML side does not style itself - tool tips, combo box
popups, menus - take their colours from here. Without it the default light
palette produced glaring white tool tips in the middle of a dark window.

It lives in its own module because both the full application and the
standalone configurator need it, and the standalone must not import the
application's bridge (that would drag in the Steam scanner, the installer
and the cover cache).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


def dark_palette() -> QPalette:
    """A dark application palette."""
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


__all__ = ["dark_palette"]
