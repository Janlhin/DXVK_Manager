"""Entry point of the standalone dxvk.conf configurator.

It mirrors :mod:`dxvk_toolkit.ui.app_qml` - the same dark palette, the same
translator handling, the same QML engine - but it loads this tool's own
window and its own bridge. The two applications never run at the same time,
so they do not share any state: the configurator keeps its own settings
file (see :mod:`dxvk_toolkit.standalone.store`) and its own data directory.

The QML components it uses are the full application's configuration
components, imported as a directory (``import "../../ui/qml" as Shared``).
Qt derives a ``qsTr()`` translation context from the *file name* of the file
the call is written in, so a shared component keeps its own context no matter
which application loads it - the English catalogue is shared as well.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTranslator, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from .. import APP_VERSION
from ..ui.palette import dark_palette
from .assets import asset_path
from .bridge import ConfiguratorBridge
from .store import settings

QML_DIR = Path(__file__).resolve().parent / "qml"

APP_NAME = "DXVK Configurator"

# The currently installed interface translator, kept so it can be swapped at
# runtime when the user changes ui_lang (hot-swap - no restart needed).
_current_translator: QTranslator | None = None
# The QML engine, set once in run(); retranslate() after a swap so qsTr()
# bindings re-evaluate (installing/removing a translator alone is not enough).
_engine: QQmlApplicationEngine | None = None


def _catalogue_path() -> Path:
    """Where the English catalogue lives.

    The configurator ships in the same tree as the full application, so it
    reads the same assets/i18n/app_en.qm. The catalogue covers both tools'
    contexts: they share the configuration components, and the extra contexts
    of this tool are simply unused by the other one.
    """
    return asset_path("i18n/app_en.qm")


def set_language(lang: str) -> None:
    """Install or remove the interface catalogue for ``lang``.

    Chinese is the source language, so zh needs no catalogue; English loads
    the compiled catalogue, which covers both the QML ``qsTr()`` strings and
    the Python ``QCoreApplication.translate()`` ones.
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
    qm = _catalogue_path()
    if not qm.is_file():
        if _engine is not None:
            _engine.retranslate()
        return
    translator = QTranslator(app)
    if translator.load(str(qm)):
        app.installTranslator(translator)
        _current_translator = translator
    if _engine is not None:
        _engine.retranslate()


def run(argv: list[str] | None = None) -> int:
    # The native Windows style refuses custom backgrounds, so the cross
    # platform "Basic" style is selected through the API: an environment
    # variable would be read too late once Qt has been imported.
    QQuickStyle.setStyle("Basic")

    app = QApplication(argv if argv is not None else sys.argv)
    set_language(str(settings.get("ui_lang") or "zh"))
    app.setPalette(dark_palette())
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("dxvk-toolkit")

    engine = QQmlApplicationEngine()
    global _engine
    _engine = engine
    # The bridge is parented to the application so it outlives this function:
    # the QML bindings call into it, and a bridge that is garbage collected
    # before the window turns every binding into a "call method of null".
    bridge = ConfiguratorBridge(parent=app)
    context = engine.rootContext()
    context.setContextProperty("bridge", bridge)
    context.setContextProperty("configModel", bridge.config)
    engine.addImportPath(str(QML_DIR))

    engine.load(QUrl.fromLocalFile(str(QML_DIR / "StandaloneMain.qml")))
    if not engine.rootObjects():
        return 1
    try:
        return app.exec()
    finally:
        _shutdown(engine, app)


def _shutdown(engine: QQmlApplicationEngine, app: QApplication) -> None:
    """Close the window before the bridge goes away.

    Destroying the QML objects while the bridge is still alive keeps the
    bindings valid until the last evaluation. Without this, the window is
    torn down after the bridge has already been collected and every binding
    reports "call method of null" on the way out.
    """
    for root in engine.rootObjects():
        root.setParent(None)
        root.deleteLater()
    app.processEvents()
    engine.clearComponentCache()


__all__ = ["run", "QML_DIR"]
