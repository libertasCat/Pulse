# 在 macOS 上运行：python -m PyInstaller --clean --noconfirm Pulse-macOS.spec
import sys
from pulse import __version__

if sys.platform != "darwin":
    raise SystemExit("Pulse-macOS.spec 必须在 macOS 上构建")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["AppKit", "Quartz", "ApplicationServices"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Pulse",
    console=False,
    argv_emulation=False,
    strip=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Pulse", strip=False, upx=False)
app = BUNDLE(
    coll,
    name="Pulse.app",
    bundle_identifier="com.libertascat.pulse",
    version=__version__,
    info_plist={
        "CFBundleName": "Pulse",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Pulse",
    },
)
