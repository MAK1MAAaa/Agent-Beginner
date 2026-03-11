# Task 1: 智能体体验与原理初探 —— 个人日程助手

## 任务目标
搭建一个具备 ReAct (Reason + Act) 能力的个人日程助手，能够：
1. 从聊天记录中提取日程。
2. 从上传的 Markdown 笔记中解析日程。
3. 执行添加、查看、修改等工具。
4. 提供简单的 Web 界面。

## 核心实现方案
- **模型**: Ollama 运行的 `qwen2.5-coder:7b`。
- **ReAct 逻辑**: 
  - **Reason**: 模型生成思考过程，分析意图与参数。
  - **Act**: 生成 `调用工具: add_schedule(time="...", task="...")` 格式。
  - **Observation**: 脚本拦截工具调用，执行 Python 代码并将结果注入 Context。
- **时间感知**: SYSTEM PROMPT 动态注入系统当前日期，帮助模型理解“明天”、“下周”等相对概念。
- **文件处理**: 支持读取本地 `test/` 目录下文件，或通过 Streamlit 上传 MD 文件并注入 Prompt。

## 目录结构
- `code/`:
  - `agent.py`: Agent 核心逻辑 (ReAct 循环)。
  - `schedule_manager.py`: 工具函数定义 (CRUD + 文件读取)。
  - `web_app.py`: 基于 Streamlit 的 Web 交互界面。
- `test/`:
  - `schedules.json`: 存储日程数据的数据库。
  - `note.md`: 测试用的示例笔记。

## 如何运行
1. **安装依赖**:
   ```bash
   uv sync
   ```
2. **启动 Web 界面**:
   ```bash
   uv run streamlit run Task1/code/web_app.py
   ```

## 实验收获
- 验证了 `qwen2.5-coder` 对 ReAct 范式的支持非常稳定。
- 意识到 SYSTEM PROMPT 中提供“当前时间上下文”对于处理日程类任务至关重要。
- 通过手动实现 ReAct 循环，深入理解了 Agent 是如何通过迭代逐步完成复杂任务（如：读文件 -> 解析 -> 多次添加 -> 回复）的。
