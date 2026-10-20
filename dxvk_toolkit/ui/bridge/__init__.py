"""The QML bridge.

``Bridge`` is the only object QML knows about; it exposes the whole feature
set as slots and signals. The implementation is split into domain services
(``library``, ``versions``, ``config``, ``settings``) plus the shared
``jobs`` infrastructure, but the facade keeps every slot signature and every
signal name unchanged, so the QML side never has to change.
"""

from .facade import Bridge

__all__ = ["Bridge"]
