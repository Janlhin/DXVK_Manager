"""QML front end (PySide6 + Qt Quick).

The core package below this one is UI-agnostic; this layer only adapts it to
Qt Quick: a QAbstractListModel for the game library and a Bridge QObject that
exposes the core operations to QML as slots and signals.
"""

from .app_qml import run

__all__ = ["run"]
