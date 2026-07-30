# Buglist

| # | 问题 | 状态 | 修复 |
|---|------|------|------|
| 1 | 程序未做单例限制，多开导致时间重复计算 | ✅ | `pulse/utils/single_instance.py` — 命名互斥体 |
| 2 | 分类点击无反应 | ✅ | `main_window.set_repo` 未调用 `settings.set_repo`；`_add_category` 改用 `repo.create_category` |
| 3 | 添加应用无反应 | ✅ | 新建分类时自动保存后再分配 |
| 4 | 颜色对话框的 OK/Cancel 按钮因主题不可见 | ✅ | `theme.py` 新增 `QColorDialog` / `QFileDialog` 专用 QSS 规则 |
| 5 | 应用图标仍是默认占位图 | ✅ | 从 DB 查询 `executable_path`，提取真实 exe 图标并缓存到磁盘 |
| 6 | 托盘右键菜单各项不可见（纯黑） | ✅ | `theme.py` 新增暗色/亮色 `QMenu` QSS 规则 |
| 7 | 开机自启设置 | ✅ | `pulse/utils/auto_start.py` 读写注册表，设置页复选框 |
| 8 | 自定义数据清理（按月） | ✅ | 设置页选择保留月数 + 立即清理按钮，弹窗确认 |
| 9 | 复选框背景和文字颜色过于一致，看不清 | ✅ | `theme.py` 新增 `QCheckBox` QSS 规则（指示器 + hover + checked 状态） |
