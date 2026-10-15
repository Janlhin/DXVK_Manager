"""Frozen-application entry point for PyInstaller.

PyInstaller bundles this script as the executable's main module and collects
the ``dxvk_toolkit`` package alongside it. We delegate to the package's real
``main()`` so all GUI/CLI logic stays in one place (running from source still
uses ``python -m dxvk_toolkit``).
"""

from dxvk_toolkit.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
