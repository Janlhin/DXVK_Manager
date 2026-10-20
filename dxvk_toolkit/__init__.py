"""DXVK Version Manager - Python edition.

A reimplementation of the DXVK version manager concept with a built-in
dxvk.conf generator. The core is standard library only; the optional QML
front end needs PySide6, and cover slicing needs Pillow.

The package is split so that every piece can be used without a GUI:

    paths       - where the app stores caches, settings and its ledger
    util        - small helpers (PE headers, sizes, logging, shell integration)
    net         - resilient HTTP with retries, proxy support and a curl fallback
    steam       - game discovery across launchers
    detect      - offline Direct3D family / architecture detection
    sources     - DXVK / DXVK-gplasync listing, download and extraction
    installer   - DLL planning, backup, install, restore and status detection
    fingerprint - identify and adopt DXVK installed by other tools
    confkit     - portable dxvk.conf toolkit (parse / curate / i18n / build)
    confspec    - app-side entry point to the config layer
    confbuild   - app-side alias for the dxvk.conf writer
    covers      - cover download plus cached card/round slices
    ui          - PySide6 + QML front end (bridge, models, config store, qml/)
"""

APP_NAME = "DXVK Version Manager"
APP_EDITION = "Python edition"
APP_VERSION = "1.0.1"

__all__ = ["APP_NAME", "APP_EDITION", "APP_VERSION"]
