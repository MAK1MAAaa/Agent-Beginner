# Task 1: 智能体体验与原理初探

## 任务目标
搭建一个个人日程助手智能体，能够从聊天记录、飞书文档或 Markdown 笔记中创建和修改日程。

## 目录结构
- `code/`: 存放智能体核心代码。
  - `agent.py`: Agent 主程序，包含 ReAct 循环逻辑。
  - `schedule_manager.py`: 日程管理工具实现。
- `test/`: 存放测试生成的文件，如 `schedules.json`。
- `README.md`: 实验记录。

## 核心实现
1. **ReAct 循环**:
   - **Reason**: 模型思考当前用户需求。
   - **Action**: 模型根据思考决定调用 `add_schedule` 或 `list_schedules`。
   - **Observation**: 脚本执行工具函数，并将结果返回给模型。
2. **工具集**:
   - `add_schedule`: 解析时间与任务并存储。
   - `list_schedules`: 列出当前所有日程。
   - `update_schedule`: 修改已有日程。

## 环境配置
- 模型：Ollama `qwen2.5-coder:7b`
- 依赖管理：`uv` (通过 `pyproject.toml`)

## 运行方式
```bash
uv run python Task1/code/agent.py
```
