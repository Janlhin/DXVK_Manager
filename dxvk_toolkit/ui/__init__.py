"""QML front end (PySide6 + Qt Quick).

The core package below this one is UI-agnostic; this layer only adapts it to
Qt Quick: a QAbstractListModel for the game library and a Bridge QObject that
exposes the core operations to QML as slots and signals.

``run`` is imported lazily: importing this package must not require PySide6,
otherwise Qt-free helpers (``config_store``) and their tests cannot run on a
machine or CI runner without the GUI dependency installed.
"""

from __future__ import annotations

__all__ = ["run"]


def run(argv: list[str] | None = None) -> int:
    """Start the QML application (imports PySide6 on first call)."""
    from .app_qml import run as _run

    return _run(argv)
