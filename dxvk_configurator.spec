# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the standalone dxvk.conf configurator.

A separate executable from the version manager: same configuration core, same
QML components, but its own name, its own window and its own settings file.

Run from the repo root::

    venv_build/Scripts/pyinstaller.exe dxvk_configurator.spec

The frozen app resolves bundled data through ``sys._MEIPASS``:
  * ``assets``                    -> DXVK conf / i18n .qm
  * ``dxvk_toolkit/ui/qml``       -> the shared QML components
  * ``dxvk_toolkit/standalone/qml`` -> the configurator's own two files
"""

import os

ROOT = os.path.abspath(SPECPATH)
ASSETS = os.path.join(ROOT, "assets")
UI_QML = os.path.join(ROOT, "dxvk_toolkit", "ui", "qml")
STANDALONE_QML = os.path.join(ROOT, "dxvk_toolkit", "standalone", "qml")

block_cipher = None

a = Analysis(
    ["pyi_launch_configurator.py"],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (ASSETS, "assets"),
        (UI_QML, "dxvk_toolkit/ui/qml"),
        (STANDALONE_QML, "dxvk_toolkit/standalone/qml"),
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickControls2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DXVK-Configurator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
