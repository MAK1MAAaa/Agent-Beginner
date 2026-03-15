# Task1: 个人日程 Agent（ReAct 实战）

## 1. 项目简介
Task1 是一个可运行的 Agent 小项目：用大模型 + 工具调用来完成「日程提取、写入、查询、修改、删除」。

你可以把它当成一个最小可用的 ReAct（Reason + Act）样例：
- 用户通过聊天输入需求，或上传 Markdown/TXT 笔记。
- Agent 分析文本后调用本地工具函数。
- 工具执行结果再反馈给 Agent，Agent 继续下一步，直到任务完成。

## 2. 能力范围
当前版本支持：
- 从聊天文本中识别日程信息并写入本地数据库。
- 从 Markdown/TXT 文档中读取内容并批量提取日程。
- 从飞书文档链接读取正文并提取日程。
- 日程管理工具：新增、修改、列出、删除（含多个新增/修改工具）。
- Streamlit 可视化界面：聊天区 + 日程侧栏 + 文件上传同步。

## 3. 核心原理（ReAct 回路）
Task1 的核心流程如下：
1. `Reason`：模型先理解用户意图（例如“明天下午开会”）。
2. `Act`：模型输出标准化工具调用文本（例如 `调用工具: add_schedule(...)`）。
3. `Observation`：程序执行该工具，并把结果回填给模型。
4. 重复以上步骤，直到模型输出最终回复（`回复:` / `结论:`）。

这个循环在 `code/agent.py` 和 `code/web_app.py` 中实现。

## 4. 目录结构
```text
Task1/
├─ code/
│  ├─ agent.py               # Agent 主循环、提示词、工具调度
│  ├─ .env                   # 模型与备用 API 配置（本地文件）
│  ├─ schedule_manager.py    # 日程数据读写、工具函数、文档读取
│  └─ web_app.py             # Streamlit 前端界面
├─ data/
│  ├─ schedules.json         # 日程数据库（运行时自动维护）
│  └─ uploads/               # 上传文件缓存目录（已从 test/uploads 迁移）
├─ test/
│  └─ note.md                # 示例测试文档
├─ pyproject.toml
└─ README.md
```

## 5. 文件读取策略
当 Agent 调用 `read_document(file_path)` 时，会按以下优先级查找文件：
1. `C:\Users\MAK1MA\Downloads`
2. `Task1/data/uploads`
3. `Task1/test`
4. `Task1/data`

这保证了上传文件（写入 `data/uploads`）能被优先读取。

当用户提供飞书文档链接时，Agent 会调用 `read_feishu_doc`，通过飞书 OpenAPI 拉取文档正文再解析日程。
当前已支持 `docx/docs/wiki` 三类链接，其中 `wiki` 会先解析节点再读取真实文档内容。

## 6. 运行方式
在 `Task1` 目录执行：

1. 安装依赖
```bash
uv sync
```

2. 配置 `code/.env`（至少配置本地模型；建议同时配置备用 API）
```env
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=qwen2.5-coder:7b
ENABLE_FALLBACK=true

FEISHU_APP_ID=
FEISHU_APP_SECRET=

FALLBACK_API_BASE_URL=
FALLBACK_API_KEY=
FALLBACK_API_MODEL=
```

3. 确保本地 Ollama 可用，并已准备模型
```bash
ollama pull qwen2.5-coder:7b
```

4. 配置飞书应用能力（读取飞书文档必需）
- 在飞书开放平台给应用开通至少以下权限：
  - `wiki:wiki:readonly`
  - `docx:document:readonly`
  - `docs:document:readonly`（旧文档兼容）
- 在飞书知识库/文档里把该应用加入可访问范围（成员/管理员或文档可见范围内）。

5. 启动 Web 界面
```bash
uv run streamlit run code/web_app.py
```

默认会请求本地接口：`http://localhost:11434/api/chat`。

## 7. 模型调用策略（本地优先 + 自动降级）
`code/agent.py` 里的调用顺序如下：
1. 先调用本地 `OLLAMA_URL`。
2. 如果本地调用失败（例如 Ollama 未启动、连接被拒绝、超时），自动尝试备用 API。
3. 备用 API 支持最多 3 组 OpenAI 兼容接口配置：
   - `FALLBACK_API_*`
   - `FALLBACK2_API_*`
   - `FALLBACK3_API_*`

每组至少需要填写：
- `*_BASE_URL`（例如 `https://api.openai.com/v1`）
- `*_API_KEY`
- `*_MODEL`

可选：
- `*_NAME`：用于错误日志区分调用来源。

## 8. 使用示例

你可以在聊天框输入：
- `帮我添加日程：明天 10:00 项目站会`
- `新增日程：2026-03-20 09:30 客户沟通`
- `把 ID 为 26031512000000000001 的日程改到明天 15:00`
- `把 ID 为 26031512000000000001 的任务改成：项目复盘会`
- `请列出我本周的日程`
- `删除 ID 为 250101... 的日程`
- `请读取这个飞书文档并同步日程：https://xxx.feishu.cn/docx/xxxxx`
- `请读取这个飞书 wiki 并同步日程：https://xxx.feishu.cn/wiki/xxxxx`

也可以上传 `md/txt` 文件后点击“开始分析并同步日程”，Agent 会自动读取并分条写入。

## 9. 当前实现特点
- 使用系统时间注入提示词，提升“明天/下周”等相对时间理解能力。
- 对工具调用采取单步执行策略，降低一次回复里多工具混用带来的混乱。
- 前端已做卡片化和信息分区，侧栏可按年月日分层浏览日程。
- 模型调用支持“本地优先 + 云端 API 兜底”，提升可用性。
- 已提供多个新增/修改工具：`add_schedule`、`add_schedule_with_date`、`update_schedule`、`reschedule_schedule`、`rename_schedule`。
- 支持读取飞书文档正文（需配置飞书应用凭据）。

## 10. 可继续扩展的方向
- 增加时间冲突检测与提醒。
- 支持重复日程（每日/每周）规则。
- 接入更严格的时间解析器与单元测试。
