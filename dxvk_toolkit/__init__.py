"""DXVK Version Manager - Python edition.

A dependency-free (standard library only) reimplementation of the DXVK version
manager concept, with a built-in dxvk.conf generator.

The package is split so that every piece can be used without a GUI:

    paths      - where the app stores caches, settings and its ledger
    util       - small helpers (PE headers, sizes, logging, shell integration)
    net        - resilient HTTP with retries, proxy support and a curl fallback
    steam      - Steam library discovery and appmanifest parsing
    metadata   - optional PCGamingWiki enrichment with an on-disk cache
    sources    - DXVK / DXVK-gplasync release listing, download and extraction
    installer  - DLL planning, backup, install, restore and status detection
    confspec   - parses a reference dxvk.conf into a UI-ready option model
    confbuild  - turns user selections back into a dxvk.conf document
    gui        - Tkinter front end
"""

APP_NAME = "DXVK Version Manager"
APP_EDITION = "Python edition"
APP_VERSION = "1.0.0"

__all__ = ["APP_NAME", "APP_EDITION", "APP_VERSION"]
