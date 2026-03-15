# NexDR Task2（改造版）

本目录是基于 NexDR 的可运行改造版，核心目标是：更可控成本、更贴近中文调试场景、保留端到端工作流。

## 主要能力
1. 搜索替换：支持 `semantic_scholar`（并兼容旧别名 `web`）。
2. 仅 Markdown：生成初稿后允许用户编辑，再由 Agent 二次改写。
3. 多输入：支持 `pdf/png/jpg/jpeg/webp/md/txt/docx`。
4. 成本分档：`micro / lite / full` 三种运行模式。

## 环境准备
```bash
uv sync
```

复制环境变量模板并填写：
```bash
cp .env.example .env
```

## 本地 Ollama（qwen3.5:9b）配置 .env
在 `Task2/nexdr_task2/.env` 中至少填写以下内容：

```dotenv
# 主 LLM（必填）
LLM_API_KEY=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen3.5:9b

# 多模态 LLM（建议与主 LLM 一致；用于图片理解/OCR 回退）
MULTI_MODAL_LLM_API_KEY=ollama
MULTI_MODAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
MULTI_MODAL_LLM_MODEL=qwen3.5:9b

# 文档解析顺序（本地文件测试建议 builtin 优先）
DOC_READER_PROVIDERS=builtin,jina,serper
PADDLEOCR_LANG=ch
```

填写要求：
1. `LLM_BASE_URL` / `MULTI_MODAL_LLM_BASE_URL` 必须以 `http://` 或 `https://` 开头，且 Ollama OpenAI 兼容地址建议写成 `http://127.0.0.1:11434/v1`。
2. `LLM_API_KEY` / `MULTI_MODAL_LLM_API_KEY` 不能留空；对于 Ollama 可填任意非空字符串（推荐 `ollama`）。
3. `LLM_MODEL` / `MULTI_MODAL_LLM_MODEL` 必须与本机已拉取模型名完全一致（这里是 `qwen3.5:9b`）。
4. 若模型本身不支持视觉能力，纯文本 PDF 仍可解析，但图片理解能力会受限。

可选：
- `SEMANTIC_SCHOLAR_API_KEY`（提高速率限制）
- `JINA_API_KEY` / `SERPER_API_KEY`（远程网页解析回退）

启动本地模型（需在另一个终端）：
```bash
ollama serve
ollama run qwen3.5:9b
```

## 三种模式（成本从低到高）
1. `micro`：最低开销，跳过深度研究循环，直接生成可用初稿。
2. `lite`：有限检索 + 精简上下文，适合大多数任务。
3. `full`：完整深度研究链路，质量更高但开销最高。

## 生成报告
```bash
uv run python quick_start.py \
  --mode generate \
  --profile micro \
  --query "请调研某主题并输出中文报告" \
  --output_dir workspaces/my_workspace \
  --input_files ./samples/a.pdf ./samples/b.png
```

## 使用 data 目录 PDF 做输入测试
你已在 `data/` 下放置两个文件：`BERT.pdf`、`Transformer.pdf`。可直接运行：

```bash
uv run python quick_start.py \
  --mode generate \
  --profile micro \
  --query "请基于附加 PDF 总结 Transformer 与 BERT 的核心思想、差异和应用建议" \
  --output_dir workspaces/ollama_pdf_test \
  --input_files data/BERT.pdf data/Transformer.pdf
```

测试通过后，重点检查：
1. `workspaces/ollama_pdf_test/final_state.json` 中 `preprocessed_docs` 的 `success` 是否为 `true`。
2. `workspaces/ollama_pdf_test/markdown_report.original.md` 是否包含来自两份 PDF 的关键信息。
3. 日志中无 `LLM environment variables are missing`、`LLM_BASE_URL is invalid` 等报错。

可选参数：
- `--history_limit 20`：限制 writer/reviser 使用的历史消息数量。

生成产物：
- `markdown_report.original.md`
- `markdown_report.md`
- `citations.json`
- `final_state.json`

## 二次改写
```bash
uv run python quick_start.py \
  --mode revise \
  --profile micro \
  --query "请根据用户修改继续完善" \
  --output_dir workspaces/my_workspace \
  --edited_markdown_path workspaces/my_workspace/markdown_report.user_edited.md
```

高开销可选：
- `--reuse_research_history`：复用研究历史以增强上下文连续性。

改写产物：
- `markdown_report.user_edited.md`
- `markdown_diff.patch`
- `markdown_diff_summary.json`
- `markdown_report.revised.md`
- `markdown_report.md`
- `citations.json`

## Streamlit 应用
```bash
uv run streamlit run demo_app.py
```

界面为单页三步骤流程：
1. 生成报告（含 `micro/lite/full` 切换）
2. 用户编辑 Markdown
3. Agent 二次改写 + 修改摘要
