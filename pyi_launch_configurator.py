"""Frozen-application entry point for the standalone configurator.

PyInstaller bundles this script as the executable's main module. It is a
separate program from the version manager: its own name, its own window, its
own settings file - but the same configuration core and the same QML
components.
"""

from dxvk_toolkit.standalone import main

if __name__ == "__main__":
    raise SystemExit(main())
