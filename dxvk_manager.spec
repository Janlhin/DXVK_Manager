# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for DXVK Version Manager (Python edition).

Produces a single-file Windows executable. Run from the repo root:

    venv_build/Scripts/pyinstaller.exe dxvk_manager.spec

The frozen app resolves bundled data through ``sys._MEIPASS``:
  * ``assets``      -> DXVK conf / i18n .qm (see dxvk_toolkit/paths.bundle_dir)
  * ``dxvk_toolkit/ui/qml`` -> QML UI (see dxvk_toolkit/ui/app_qml.QML_DIR)
"""

import os

ROOT = os.path.abspath(SPECPATH)
ASSETS = os.path.join(ROOT, "assets")
QML = os.path.join(ROOT, "dxvk_toolkit", "ui", "qml")

block_cipher = None

a = Analysis(
    ["pyi_launch.py"],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (ASSETS, "assets"),
        (QML, "dxvk_toolkit/ui/qml"),
    ],
    hiddenimports=[
        # Qt submodules referenced from Python are auto-detected. The QML
        # modules used by the .qml files (QtQuick / QtQuick.Controls /
        # QtQuick.Layouts) are collected by PyInstaller's PySide6 / QtQuick
        # Controls 2 hooks once those Python packages are imported by the app
        # (see dxvk_toolkit/ui/app_qml.py: PySide6.QtQml, PySide6.QtQuickControls2).
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
    name="DXVK-Version-Manager",
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
