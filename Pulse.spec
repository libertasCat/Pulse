# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys

conda_bin = Path(sys.base_prefix) / 'Library' / 'bin'
system32 = Path(os.environ['WINDIR']) / 'System32'
# PyInstaller 会沿 PATH 搜索间接 DLL。构建机上其他工具携带的 ICU/Qt DLL
# 可能被错误收集，因此发布构建只允许当前 Python、Conda 运行库和系统目录。
os.environ['PATH'] = os.pathsep.join([
    str(Path(sys.executable).parent), str(conda_bin), str(system32),
    str(Path(os.environ['WINDIR'])),
])

# 固定使用 Windows 已安装的 VC++ Redistributable，不使用 Conda 环境中可能回退的版本。
# QtGui.pyd 对较新运行库符号有依赖；较旧的 app-local DLL 会遮蔽系统 DLL 并导致导入失败。
vc_runtime_dlls = [
    'concrt140.dll',
    'msvcp140.dll',
    'msvcp140_1.dll',
    'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll',
    'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll',
    'vcruntime140_1.dll',
    'vcruntime140_threads.dll',
]

binaries = [
    (str(conda_bin / 'libcrypto-3-x64.dll'), '.'),
    (str(conda_bin / 'libssl-3-x64.dll'), '.'),
]
binaries += [
    (str(system32 / dll), '.')
    for dll in vc_runtime_dlls
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
