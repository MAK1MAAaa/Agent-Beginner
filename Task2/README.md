# Task2 总览：相对原版 NexDR 的改造对比

本文用于说明 `Task2` 中我们对原版 NexDR 的改造范围、目录结构和差异点。

## 目录结构
- `upstream_nexdr/`：原版快照（基线，对照用）
- `nexdr_task2/`：改造后的可运行版本

## 基线信息
- 上游仓库：`nex-agi/NexDR`
- 基线快照：`94d2718`
- Python：`3.12`
- 包管理：`uv`

## 你要求的三项改造，对比结果

### 1) 搜索替换（Semantic Scholar）
原版：
- 依赖通用 Web 搜索链路。

Task2 改造：
- 新增 `semantic_scholar_search.py`。
- `search.py` 支持 `semantic_scholar`，并保留 `web -> semantic_scholar` 兼容映射。
- 更新 `Search.tool.yaml`，将新搜索源纳入可选项。
- 结果统一映射到现有 `resources` 结构，兼容后续引用流程。

### 2) 仅 Markdown + 用户编辑后二次改写
原版：
- 支持 Markdown/HTML 等多种输出路径。

Task2 改造：
- `quick_start.py` 收敛为 Markdown 主流程。
- 新增 `--mode generate|revise`：
  - `generate`：生成 `markdown_report.original.md`
  - `revise`：读取用户编辑稿并做二次改写
- 固定产物：
  - `markdown_report.original.md`
  - `markdown_report.user_edited.md`
  - `markdown_diff.patch`
  - `markdown_diff_summary.json`
  - `markdown_report.revised.md`
  - `citations.json`
- Streamlit 改为三栏：生成 -> 编辑 -> 改写。

### 3) 多输入（PDF/图片等）
原版：
- 输入类型和本地预处理能力有限。

Task2 改造：
- 扩展本地文件解析：`pdf/png/jpg/jpeg/webp/md/txt/docx`。
- PDF 优先本地解析（PyMuPDF）。
- 图片优先 OCR（可选 PaddleOCR），失败时回退多模态描述。
- 文档预处理支持“本地优先、远程回退”策略。

## 新增成本控制（额外增强）
为解决高 token 消耗，Task2 增加运行档位：
- `micro`：最低开销，直接生成可用稿
- `lite`：平衡质量和成本
- `full`：完整深度链路

涉及修改：
- `quick_start.py`：新增 `--profile micro|lite|full`
- 新增精简配置：
  - `configs/deep_research/deep_research_lite.yaml`
  - `configs/markdown_report_writer/report_writer_lite.yaml`
  - `configs/markdown_reviser/reviser_lite.yaml`
- `demo_app.py`：前端支持 profile 切换

## 关键命令
在 `Task2/nexdr_task2` 目录：

安装：
```bash
uv sync
```

低开销生成：
```bash
uv run python quick_start.py --mode generate --profile micro --query "你的问题"
```

二次改写：
```bash
uv run python quick_start.py \
  --mode revise \
  --profile micro \
  --output_dir workspaces/你的工作区 \
  --edited_markdown_path workspaces/你的工作区/markdown_report.user_edited.md
```

Streamlit：
```bash
uv run streamlit run demo_app.py
```
