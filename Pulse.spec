# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

import PyQt6


qt_bin = Path(PyQt6.__file__).resolve().parent / 'Qt6' / 'bin'
conda_bin = Path(sys.prefix) / 'Library' / 'bin'

# PyInstaller 会收集 Qt6Core/Gui/Widgets，但会把以下 DLL 当作系统运行库而省略。
# 在未安装 VC++ 开发环境的 Windows 机器上，这会导致导入 PyQt6.QtGui 失败。
qt_runtime_dlls = [
    'concrt140.dll',
    'd3dcompiler_47.dll',
    'msvcp140_1.dll',
    'msvcp140_atomic_wait.dll',
    'msvcp140_codecvt_ids.dll',
    'vcruntime140_threads.dll',
]

binaries = [
    (str(conda_bin / 'libcrypto-3-x64.dll'), '.'),
    (str(conda_bin / 'libssl-3-x64.dll'), '.'),
]
binaries += [
    (str(qt_bin / dll), 'PyQt6/Qt6/bin')
    for dll in qt_runtime_dlls
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Pulse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Pulse',
)
