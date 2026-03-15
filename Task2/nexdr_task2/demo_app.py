"""Task2 Streamlit app: generate markdown -> user edit -> agent revise."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACES_DIR = PROJECT_ROOT / "workspaces"

PROFILE_META = {
    "micro": {
        "label": "Micro",
        "desc": "最低开销，直接出可用初稿",
        "hint": "适合先拿结果、快速迭代",
    },
    "lite": {
        "label": "Lite",
        "desc": "平衡质量与成本，有限检索",
        "hint": "适合常规调研任务",
    },
    "full": {
        "label": "Full",
        "desc": "最深分析，开销最高",
        "hint": "适合高价值、高复杂任务",
    },
}

STEP_META = [
    ("generate", "1) 生成报告", "创建工作区并产出初稿"),
    ("edit", "2) 编辑 Markdown", "人工修订与下载中间稿"),
    ("revise", "3) Agent 二次改写", "基于修改稿自动重写并对比"),
]


st.set_page_config(
    page_title="NexDR Task2 Studio",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

:root {
  --bg-1: #ffffff;
  --bg-2: #ffffff;
  --panel: #ffffff;
  --ink: #1f2a2e;
  --muted: #6a7175;
  --line: #d9dee3;
  --accent: #116466;
  --accent-2: #c0523f;
  --accent-3: #d4a35f;
}

.stApp {
  background: #ffffff;
  color: var(--ink);
}

div.block-container {
  max-width: 1380px;
  padding-top: 2.4rem;
  padding-bottom: 2.4rem;
}

h1, h2, h3, h4 {
  font-family: "Cormorant Garamond", "Times New Roman", serif;
  letter-spacing: 0.2px;
  color: var(--ink);
}

p, label, div, textarea, input, button {
  font-family: "Source Sans 3", "Segoe UI", sans-serif;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: linear-gradient(120deg, #ffffff, #f7f9fb);
  box-shadow: 0 10px 22px rgba(20, 30, 40, 0.06);
  padding: 12px 16px;
  margin-top: 0.65rem;
  margin-bottom: 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  width: 22px;
  height: 22px;
  border-radius: 7px;
  background: linear-gradient(135deg, var(--accent), #2e8f92);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.brand-title {
  font-family: "Cormorant Garamond", "Times New Roman", serif;
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.chip {
  display: inline-block;
  border: 1px solid var(--accent);
  color: var(--accent);
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 12px;
  margin-left: 6px;
}

.metric-box {
  border-left: 4px solid var(--accent-2);
  border-radius: 8px;
  background: rgba(255, 241, 231, 0.9);
  padding: 8px 10px;
  margin-bottom: 8px;
}

.helper {
  color: var(--muted);
  font-size: 12px;
}

.step-note {
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 13px;
}

.status-line {
  color: var(--muted);
  font-size: 12px;
  margin-top: 4px;
  margin-bottom: 10px;
}

.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--accent), #2e8f92);
  border-color: var(--accent);
  color: #ffffff;
  font-weight: 700;
}

.stButton > button[kind="secondary"] {
  border: 1px solid #cdd7df;
  background: #ffffff;
  color: #3d4a50;
}

.stButton > button[kind="secondary"]:hover {
  border-color: #8fa5b5;
  color: #203038;
}

[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {
  display: none !important;
}

@media (max-width: 960px) {
  .brand-title { font-size: 24px; }
  .topbar { flex-direction: column; align-items: flex-start; gap: 8px; }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<section class="topbar">
  <div class="brand">
    <span class="brand-mark">N</span>
    <div>
      <div class="brand-title">Task2：NexDR Research Studio</div>
    </div>
  </div>
</section>
""",
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults = {
        "active_step": "generate",
        "workspace": "",
        "query": "请调研该主题并生成结构化中文报告",
        "profile": "micro",
        "history_limit": -1,
        "reuse_research_history": False,
        "generate_logs": "",
        "revise_logs": "",
        "original_md": "",
        "edited_md": "",
        "revised_md": "",
        "diff_summary": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _create_workspace() -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    workspace = WORKSPACES_DIR / f"workspace_{stamp}"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _save_uploads(uploaded_files: list, workspace: Path) -> list[str]:
    if not uploaded_files:
        return []
    upload_dir = workspace / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for file in uploaded_files:
        dst = upload_dir / file.name
        dst.write_bytes(file.read())
        saved_paths.append(str(dst))
    return saved_paths


def _read_if_exists(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _load_workspace_outputs(workspace: Path) -> None:
    st.session_state["original_md"] = _read_if_exists(
        workspace / "markdown_report.original.md"
    )
    if not st.session_state["edited_md"]:
        st.session_state["edited_md"] = st.session_state["original_md"]
    st.session_state["revised_md"] = _read_if_exists(
        workspace / "markdown_report.revised.md"
    )
    summary_path = workspace / "markdown_diff_summary.json"
    if summary_path.exists():
        st.session_state["diff_summary"] = json.loads(
            summary_path.read_text(encoding="utf-8")
        )


def _run_generate(
    query: str,
    workspace: Path,
    input_files: list[str],
    profile: str,
    history_limit: int,
) -> tuple[bool, str]:
    cmd = [
        "uv",
        "run",
        "python",
        "quick_start.py",
        "--mode",
        "generate",
        "--profile",
        profile,
        "--query",
        query,
        "--output_dir",
        str(workspace),
    ]
    if history_limit > 0:
        cmd += ["--history_limit", str(history_limit)]
    if input_files:
        cmd += ["--input_files", *input_files]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    logs = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode == 0, logs.strip()


def _run_revise(
    query: str,
    workspace: Path,
    edited_markdown: str,
    profile: str,
    history_limit: int,
    reuse_research_history: bool,
) -> tuple[bool, str]:
    edited_path = workspace / "markdown_report.user_edited.md"
    edited_path.write_text(edited_markdown, encoding="utf-8")
    cmd = [
        "uv",
        "run",
        "python",
        "quick_start.py",
        "--mode",
        "revise",
        "--profile",
        profile,
        "--query",
        query,
        "--output_dir",
        str(workspace),
        "--edited_markdown_path",
        str(edited_path),
    ]
    if history_limit > 0:
        cmd += ["--history_limit", str(history_limit)]
    if reuse_research_history:
        cmd.append("--reuse_research_history")
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    logs = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode == 0, logs.strip()


def _render_diff_summary(summary: dict) -> None:
    if not summary:
        st.info("暂无修改摘要。先执行一次二次改写。")
        return
    st.markdown(
        f"""
<div class="metric-box"><strong>新增段落</strong>: {summary.get("added_paragraphs", 0)}</div>
<div class="metric-box"><strong>删除段落</strong>: {summary.get("removed_paragraphs", 0)}</div>
<div class="metric-box"><strong>改写段落</strong>: {summary.get("modified_paragraphs", 0)}</div>
<div class="metric-box"><strong>新增行 / 删除行</strong>: {summary.get("added_lines", 0)} / {summary.get("removed_lines", 0)}</div>
""",
        unsafe_allow_html=True,
    )


_init_state()

step_labels = {step: label for step, label, _ in STEP_META}
step_hints = {step: hint for step, _, hint in STEP_META}
step_options = [step for step, _, _ in STEP_META]

st.markdown("#### 步骤导航")
nav_cols = st.columns(3, gap="small")
for idx, step in enumerate(step_options):
    with nav_cols[idx]:
        clicked = st.button(
            step_labels[step],
            key=f"step_nav_{step}",
            use_container_width=True,
            type="primary" if st.session_state["active_step"] == step else "secondary",
        )
        if clicked and st.session_state["active_step"] != step:
            st.session_state["active_step"] = step
            st.rerun()
st.markdown(
    f'<div class="step-note">{step_hints[st.session_state["active_step"]]}</div>',
    unsafe_allow_html=True,
)
workspace_text = st.session_state["workspace"] if st.session_state["workspace"] else "尚未创建"
st.markdown(
    f'<div class="status-line">Workspace: {workspace_text} | '
    f'Profile: {st.session_state["profile"]} | '
    f'history_limit: {st.session_state["history_limit"]}</div>',
    unsafe_allow_html=True,
)


def _render_generate_panel() -> None:
    st.markdown(
        """
<div class="panel-head">
  <h3>1) 生成报告</h3>
  <div><span class="chip">Generate</span><span class="chip">Files+</span></div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.session_state["query"] = st.text_area(
        "研究问题",
        value=st.session_state["query"],
        height=120,
    )
    st.session_state["profile"] = st.selectbox(
        "模式",
        options=["micro", "lite", "full"],
        index=["micro", "lite", "full"].index(st.session_state["profile"]),
        format_func=lambda x: f"{PROFILE_META[x]['label']} - {PROFILE_META[x]['desc']}",
    )
    st.caption(PROFILE_META[st.session_state["profile"]]["hint"])
    st.session_state["history_limit"] = st.number_input(
        "history_limit（可选）",
        min_value=-1,
        max_value=300,
        value=int(st.session_state["history_limit"]),
        step=1,
        help="-1 表示按模式默认值；正整数会限制 writer/reviser 输入历史消息数量。",
    )
    uploaded_files = st.file_uploader(
        "上传补充材料",
        type=["pdf", "png", "jpg", "jpeg", "webp", "md", "txt", "docx"],
        accept_multiple_files=True,
    )
    if st.button("运行生成", type="primary", use_container_width=True):
        workspace = _create_workspace()
        st.session_state["workspace"] = str(workspace)
        input_files = _save_uploads(uploaded_files or [], workspace)
        with st.spinner("正在生成 markdown 报告..."):
            ok, logs = _run_generate(
                st.session_state["query"],
                workspace,
                input_files,
                st.session_state["profile"],
                int(st.session_state["history_limit"]),
            )
        st.session_state["generate_logs"] = logs
        _load_workspace_outputs(workspace)
        if ok:
            st.success(f"生成完成: {workspace}")
            st.session_state["active_step"] = "edit"
            st.rerun()
        else:
            st.error("生成失败，请查看日志。")
    st.text_area("生成日志", value=st.session_state["generate_logs"], height=280)


def _render_edit_panel() -> None:
    st.markdown(
        """
<div class="panel-head">
  <h3>2) 编辑 Markdown</h3>
  <div><span class="chip">Editable</span></div>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button("载入原始稿", use_container_width=True):
        workspace = (
            Path(st.session_state["workspace"]) if st.session_state["workspace"] else None
        )
        if workspace and workspace.exists():
            st.session_state["edited_md"] = _read_if_exists(
                workspace / "markdown_report.original.md"
            )
        else:
            st.warning("请先运行生成。")
    st.session_state["edited_md"] = st.text_area(
        "Markdown（可直接修改）",
        value=st.session_state["edited_md"],
        height=560,
    )
    if st.session_state["edited_md"]:
        st.download_button(
            "下载当前编辑稿",
            data=st.session_state["edited_md"],
            file_name="markdown_report.user_edited.md",
            mime="text/markdown",
            use_container_width=True,
        )
    if st.button("进入二次改写", use_container_width=True):
        st.session_state["active_step"] = "revise"
        st.rerun()


def _render_revise_panel() -> None:
    st.markdown(
        """
<div class="panel-head">
  <h3>3) Agent 二次改写</h3>
  <div><span class="chip">Revise</span><span class="chip">Diff</span></div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.session_state["reuse_research_history"] = st.checkbox(
        "复用 research history（开销更高）",
        value=bool(st.session_state["reuse_research_history"]),
    )
    st.caption("默认关闭更省 token。只有需要强上下文连续性时再开启。")
    if st.button("执行二次改写", type="primary", use_container_width=True):
        workspace = (
            Path(st.session_state["workspace"]) if st.session_state["workspace"] else None
        )
        if not workspace or not workspace.exists():
            st.error("请先生成报告。")
        elif not st.session_state["edited_md"].strip():
            st.error("编辑区为空，无法改写。")
        else:
            with st.spinner("正在识别修改并二次改写..."):
                ok, logs = _run_revise(
                    st.session_state["query"],
                    workspace,
                    st.session_state["edited_md"],
                    st.session_state["profile"],
                    int(st.session_state["history_limit"]),
                    bool(st.session_state["reuse_research_history"]),
                )
            st.session_state["revise_logs"] = logs
            _load_workspace_outputs(workspace)
            if ok:
                st.success("改写完成。")
            else:
                st.error("改写失败，请查看日志。")
    st.markdown("#### 识别到的修改摘要")
    _render_diff_summary(st.session_state["diff_summary"])
    st.text_area("改写日志", value=st.session_state["revise_logs"], height=150)
    st.markdown("#### 改写结果")
    st.markdown(st.session_state["revised_md"] or "_暂无改写结果_")
    if st.session_state["revised_md"]:
        st.download_button(
            "下载改写稿",
            data=st.session_state["revised_md"],
            file_name="markdown_report.revised.md",
            mime="text/markdown",
            use_container_width=True,
        )


if st.session_state["active_step"] == "generate":
    _render_generate_panel()
elif st.session_state["active_step"] == "edit":
    _render_edit_panel()
else:
    _render_revise_panel()
