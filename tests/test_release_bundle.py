"""Windows 发布目录完整性检查。"""

from pathlib import Path


REQUIRED_QT_RUNTIME_DLLS = {
    "concrt140.dll",
    "d3dcompiler_47.dll",
    "msvcp140_1.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcruntime140_threads.dll",
}


def assert_release_bundle(root: Path) -> None:
    qt_bin = root / "_internal" / "PyQt6" / "Qt6" / "bin"
    missing = sorted(name for name in REQUIRED_QT_RUNTIME_DLLS if not (qt_bin / name).is_file())
    assert not missing, f"发布包缺少 Qt 运行库: {', '.join(missing)}"
    assert (root / "Pulse.exe").is_file(), "发布包缺少 Pulse.exe"


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    assert_release_bundle(project_root / "dist" / "Pulse")
    print("发布目录 DLL 完整性检查通过")
