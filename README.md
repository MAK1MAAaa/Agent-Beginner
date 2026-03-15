# Agent-Beginner

学习型 Agent 项目集合，当前包含两个完整任务：
1. `Task1`：个人日程 Agent（ReAct + 工具调用 + Streamlit）
2. `Task2`：NexDR 改造版（Markdown 工作流 + 多输入 + 成本分档）

## Task1 完成内容（个人日程 Agent）
1. 实现了可运行的 ReAct 闭环：`Reason -> Act -> Observation -> Final`。
2. 完成日程工具链：新增、修改、改期、重命名、查询、删除。
3. 支持多种输入来源：聊天文本、Markdown/TXT 上传、飞书文档链接。
4. 支持“本地模型优先 + 备用 API 自动降级”策略，增强可用性。
5. 提供 Streamlit 前端，包含对话区和日程可视化侧栏。

详细文档：`Task1/README.md`

## Task2 完成内容（NexDR 改造）
1. 搜索能力改造：接入 `semantic_scholar`，兼容旧 `web` 别名。
2. 输出流程收敛为 Markdown：支持 `generate` 初稿和 `revise` 二次改写。
3. 扩展多输入预处理：支持 `pdf/png/jpg/jpeg/webp/md/txt/docx`。
4. 增加成本分档：`micro / lite / full`，用于控制质量与 token 开销。
5. 新增本地 Ollama 配置方案：支持 `qwen3.5:9b`，并给出 `.env` 填写规范。
6. 已使用 `data/BERT.pdf` 和 `data/Transformer.pdf` 完成输入链路实测。
7. Streamlit 页面改造为单页三步骤流程（生成 -> 编辑 -> 改写）。

详细文档：`Task2/README.md` 与 `Task2/nexdr_task2/README.md`

## 快速开始
### Task1
```bash
cd Task1
uv sync
uv run streamlit run code/web_app.py
```

### Task2
```bash
cd Task2/nexdr_task2
uv sync
uv run streamlit run demo_app.py
```

## 思考题回答
### 1. 熟悉 MCP 和 Skills，总结常见使用方法
1. 先按任务拆分能力：检索、执行、写作、评估分别映射到不同 MCP 工具或 Skills。
2. 把高频流程沉淀为 Skill：输入约束、执行步骤、输出模板固定化，降低提示词波动。
3. 使用“最小可用工具集”：每轮只暴露必要工具，降低误调用和上下文噪声。
4. 工具调用优先结构化：参数显式、返回格式固定，避免自由文本解析失败。
5. 建立可观测闭环：记录每次工具调用、耗时、错误类型，持续优化 Skill 说明和路由规则。

### 2. 如何提高 Agent 部署时显卡使用率及运行效率
1. 推理引擎选型：优先使用支持 continuous batching 的引擎（如 vLLM 类方案）。
2. 提升并发和批处理：合并短请求、设置合理队列，避免 GPU 长时间空转。
3. 控制上下文长度：缩短无效历史、做检索裁剪，减少显存和计算浪费。
4. 精度与量化：根据质量要求使用 FP16/BF16/INT4，平衡吞吐与效果。
5. 数据流水并行：把文档解析、检索、后处理异步化，让 CPU 与 GPU 并行工作。
6. 监控驱动调参：持续看 `GPU util`、`显存占用`、`tokens/s`、`首 token 延迟`，按瓶颈调 batch 和并发。

### 3. 如何利用环境反馈训练更好的 Agent
1. 全量记录轨迹：保存 `用户输入 -> 工具调用 -> 结果 -> 最终输出 -> 成败标签`。
2. 构建偏好数据：把成功轨迹作为正样本、失败轨迹作为负样本，形成可训练数据集。
3. 先做行为克隆（SFT）：让模型先学会稳定复现“正确工具链”。
4. 再做偏好优化（DPO/RL）：用环境奖励信号优化策略，减少无效步骤与错误调用。
5. 建立自动评测集：按真实场景分层（简单/复杂/长上下文/多工具），持续回归测试。
6. 做困难样本回灌：重点训练历史高失败率问题，迭代提升在真实环境中的鲁棒性。
