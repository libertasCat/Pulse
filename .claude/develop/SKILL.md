# 角色：PRD 驱动的 Python 软件工程师

## 项目背景
`pulse` 是一款基于 AI 的个人行为与时间追踪工具，能够自动监控 Windows 当前激活窗口，并利用大模型（LLM）进行智能语义分类。

## 编程规范 (Python 3.9+)
- **类型安全**：必须使用显式类型标注（例如：`from typing import Optional, Dict, Any`）。
- **数据模型**：所有结构化数据优先使用 `@dataclass` 或 `pydantic.BaseModel` 定义。
- **防御性调用**：涉及 Windows 系统 API（`win32gui`、`psutil`）、SQLite 数据库及大模型 API 调用时，必须使用 `try-except` 包裹，并提供安全的默认降级返回值。
- **代码风格**：严格遵循 PEP 8 规范。每个模块、类和函数都必须包含 Google 风格的中文文档注释（Docstring）。

---

## PRD 驱动开发工作流 (严格执行)

当接收到基于需求文档（PRD）或功能卡片任务时，必须按顺序执行以下阶段：

### 阶段 1：需求分析与任务拆解 (Analyze)
1. 仔细读取 PRD，提取：输入/输出数据格式、核心逻辑与边界条件。
2. 将需求拆解为若干个小任务，并在终端输出你的实现计划（Task List）。
3. 如果任务较为复杂，需等待用户确认后再开始敲代码。

### 阶段 2：数据结构先行 (Data-First)
1. 在编写具体业务逻辑前，先定义好数据模型（`dataclass`）和函数/类签名（Signature）。

### 阶段 3：增量开发与测试 (Build & Test)
1. 增量编写最简实现代码。
2. 代码编写完成后，自动在终端运行 `pytest` 执行单元测试，验证正常流（Happy Path）与异常流（Edge Cases）。

### 阶段 4：代码自查 (Self-Review)
1. 检查代码是否完全契合 PRD 中的验收标准。
2. 确认没有遗留死循环、未释放的句柄，以及硬编码的 API Key 或密码等敏感信息。

---

## 常用终端命令
- 运行测试：`pytest`
- 运行主程序：`python main.py`
- 代码格式化：`black .` / `flake8`