"""Shared plumbing for the bridge services.

The services behind the QML facade are plain Python objects, not QObjects:
every signal and every slot QML can see stays on the facade
(:mod:`dxvk_toolkit.ui.bridge.facade`). A service reaches the facade through
``self._host``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QCoreApplication

# The catalogue (assets/i18n/app_en.ts) stores every Python-side string under
# the "Bridge" context, because the strings used to live in a single QObject
# named Bridge. QObject.tr() derives the context from the class name, so the
# services - which are plain classes - must pin the context themselves or the
# English catalogue silently stops matching.
TRANSLATION_CONTEXT = "Bridge"


class BridgeService:
    """Base class for the domain services behind the facade."""

    def __init__(self, host: Any) -> None:
        self._host = host

    # -- text -----------------------------------------------------------
    def tr(self, text: str) -> str:
        """Translate a UI string under the shared "Bridge" context."""
        return QCoreApplication.translate(TRANSLATION_CONTEXT, text)

    # -- plumbing -------------------------------------------------------
    def _submit(
        self,
        work: Callable[[], Any],
        done: Callable[[Any], None],
        error_label: str | None,
        quiet: bool = False,
        *,
        pool: Any = None,
        on_error: Any = None,
    ) -> None:
        """Run ``work`` off the interface thread and ``done`` on it."""
        self._host._submit(work, done, error_label, quiet, pool=pool, on_error=on_error)

    def _set_busy(self, value: bool) -> None:
        self._host._set_busy(value)

    def _status(self, text: str, kind: str = "info") -> None:
        self._host.statusMessage.emit(text, kind)

    def _progress(self, value: float, label: str = "") -> None:
        self._host.progressChanged.emit(value, label)

    # -- task de-duplication --------------------------------------------
    def _claim(self, group: str, key: str) -> bool:
        """Reserve ``key`` in ``group``; False when it was already in flight."""
        return self._host._jobs.claim(group, key)

    def _release(self, group: str, key: str) -> None:
        self._host._jobs.release(group, key)
