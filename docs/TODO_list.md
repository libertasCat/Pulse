# TODO List

| #  | 任务             | 状态 | 说明 |
|----|----------------|------|------|
| 1  | 柱状图显示应用图标      | ✅ | exe 图标提取 + 缓存到 `~/.pulse/icons/` |
| 2  | 手动分类           | ✅ | 自定义分类（名称+颜色+图标），独立页面 |
| 3  | 往分类中添加应用改为文件选择器方式 | ✅ | `QFileDialog` 选取 `.exe` |
| 4  | 分类独立页面 + 自定义图标 | ✅ | 侧边栏「分类」页，24 预设 emoji 图标 |
| 5  | 优化界面样式         | ✅ | 卡片 hover 态、间距、QColorDialog/QFileDialog 主题适配 |
| 6  | 设置 Pulse 应用图标  | ✅ | 紫色渐变 P 字图标，已用于窗口和系统托盘 |
| 7  | DeepSeek API 集成 | ✅ | `pulse/services/llm_client.py` + `pulse/core/classifier.py`，设置页配置 Key |
| 8  | AI 自动分类按钮      | ✅ | 分类页面「🤖 AI 自动分类」，调用 DeepSeek 批量分类 |
| 9  | 开机自启           | ✅ | 设置页复选框，写 Windows 注册表 |
| 10 | 数据清理           | ✅ | 设置页按月保留 + 手动触发 |