"""Windows 发布配置完整性检查。"""

from pathlib import Path


REQUIRED_QT_RUNTIME_DLLS = {
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcruntime140_threads.dll",
}


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    spec = (project_root / "Pulse.spec").read_text(encoding="utf-8")
    missing = sorted(name for name in REQUIRED_QT_RUNTIME_DLLS if repr(name) not in spec)
    assert not missing, f"打包配置缺少 Qt 运行库: {', '.join(missing)}"
    assert "system32" in spec, "VC++ 运行库必须来自已安装的系统 Redistributable"
    assert "exclude_binaries=True" in spec, "Windows 完整版应使用 onedir 模式"
    assert "COLLECT(" in spec, "onedir 模式必须创建 COLLECT 目录"
    print("发布配置完整性检查通过")
