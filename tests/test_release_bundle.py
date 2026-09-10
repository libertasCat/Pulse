"""Windows 发布配置完整性检查。"""

from pathlib import Path


REQUIRED_QT_RUNTIME_DLLS = {
    "concrt140.dll",
    "d3dcompiler_47.dll",
    "msvcp140_1.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcruntime140_threads.dll",
}


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    spec = (project_root / "Pulse.spec").read_text(encoding="utf-8")
    missing = sorted(name for name in REQUIRED_QT_RUNTIME_DLLS if repr(name) not in spec)
    assert not missing, f"打包配置缺少 Qt 运行库: {', '.join(missing)}"
    assert "exclude_binaries=False" in spec, "Windows 发布包必须使用单文件模式"
    assert "COLLECT(" not in spec, "单文件模式不应创建 COLLECT 目录"
    print("单文件发布配置完整性检查通过")
