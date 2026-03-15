import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import streamlit as st

# 确保 code 目录在 path 中
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

from agent import build_tools_description, call_ollama, execute_tool, get_system_prompt
from schedule_manager import UPLOADS_DIR, delete_schedule, load_schedules, save_schedules

st.set_page_config(page_title="智能日程助手 Agent", page_icon="🧭", layout="wide")


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    if "max_iters" not in st.session_state:
        st.session_state.max_iters = 10


def parse_schedule_time(time_str: str):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return None


def get_sorted_schedules():
    parsed_data = []
    for schedule in load_schedules():
        dt = parse_schedule_time(schedule.get("time", "")) or datetime.max
        parsed_data.append(
            {
                "id": str(schedule.get("id")),
                "time_str": schedule.get("time", ""),
                "task": schedule.get("task", ""),
                "dt": dt,
            }
        )
    parsed_data.sort(key=lambda item: (item["dt"], item["id"]))
    return parsed_data


def sort_mixed_keys(keys, reverse_int=False):
    int_keys = sorted([key for key in keys if isinstance(key, int)], reverse=reverse_int)
    other_keys = sorted([key for key in keys if not isinstance(key, int)])
    return int_keys + other_keys


def render_theme():
    st.markdown(
        """
        <style>
        :root {
            --bg-main: #f8f5ee;
            --bg-card: #fffdf8;
            --ink-strong: #1f2435;
            --ink-soft: #59607a;
            --line: #d8d0be;
            --accent: #1747b2;
            --accent-soft: #e6edff;
            --shadow: 0 16px 34px rgba(25, 35, 63, 0.10);
            --radius-lg: 18px;
            --radius-md: 12px;
        }

        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 4% 8%, rgba(31, 74, 194, 0.10), transparent 42%),
                radial-gradient(circle at 92% 26%, rgba(250, 200, 73, 0.14), transparent 36%),
                linear-gradient(140deg, #f5f2ea 0%, #f8f5ee 55%, #f1ede3 100%);
            color: var(--ink-strong);
            font-family: "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", sans-serif;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(170deg, rgba(255, 253, 248, 0.98) 0%, rgba(244, 239, 228, 0.97) 100%);
            border-right: 1px solid var(--line);
        }

        .main .block-container {
            padding-top: 1.8rem;
            padding-bottom: 8rem;
            max-width: 1180px;
        }

        .hero-card {
            background: linear-gradient(118deg, rgba(14, 31, 82, 0.97) 0%, rgba(23, 71, 178, 0.95) 66%, rgba(250, 205, 87, 0.93) 180%);
            color: #f9fbff;
            border-radius: 22px;
            padding: 1.7rem 1.9rem 1.5rem 1.9rem;
            box-shadow: 0 18px 36px rgba(15, 26, 55, 0.24);
            border: 1px solid rgba(255, 255, 255, 0.15);
            animation: rise 0.55s ease-out both;
            margin-bottom: 1rem;
        }

        .hero-card h1 {
            margin: 0 0 0.45rem 0;
            font-size: 2.05rem;
            line-height: 1.08;
            font-family: "STZhongsong", "Songti SC", "Noto Serif CJK SC", serif;
            letter-spacing: 0.02em;
        }

        .hero-eyebrow {
            margin: 0 0 0.55rem 0;
            letter-spacing: 0.11em;
            font-size: 0.72rem;
            text-transform: uppercase;
            color: rgba(241, 246, 255, 0.85);
        }

        .hero-sub {
            margin: 0;
            color: rgba(244, 247, 255, 0.86);
            max-width: 64ch;
            font-size: 0.96rem;
        }

        .hero-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin-top: 1rem;
        }

        .hero-chip {
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.22);
            background: rgba(243, 248, 255, 0.16);
            padding: 0.4rem 0.78rem;
            font-size: 0.84rem;
            color: #fcfdff;
            backdrop-filter: blur(3px);
        }

        .section-label {
            margin: 0.75rem 0 0.35rem 0;
            color: var(--ink-soft);
            letter-spacing: 0.08em;
            font-size: 0.72rem;
            text-transform: uppercase;
            font-weight: 700;
        }

        [data-testid="stVerticalBlock"] [data-testid="stChatMessage"] {
            border: 1px solid var(--line);
            border-radius: var(--radius-md);
            background: color-mix(in srgb, var(--bg-card) 90%, white);
            box-shadow: 0 5px 14px rgba(0, 0, 0, 0.04);
        }

        [data-testid="stFileUploader"],
        [data-testid="stExpander"],
        [data-testid="stStatusWidget"],
        [data-testid="stMetric"] {
            border-radius: var(--radius-md);
        }

        [data-testid="stExpander"] {
            border: 1px solid #d7d0bf;
            background: rgba(255, 253, 248, 0.82);
            margin-bottom: 0.35rem;
        }

        [data-testid="stExpander"] details summary {
            font-weight: 600;
            color: #27304b;
        }

        [data-testid="stSidebar"] [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.55);
            border: 1px solid #ddd6c6;
            padding: 0.2rem 0.6rem;
        }

        [data-testid="stSidebar"] [data-testid="stMetricValue"] {
            color: #1e325f;
            font-weight: 700;
        }

        .stChatInputContainer > div {
            background: rgba(252, 250, 244, 0.96);
            border-top: 1px solid #d8cfbc;
        }

        .stTextInput > div > div > input,
        [data-testid="stChatInput"] textarea {
            background: #fffcf5;
            border: 1px solid #d4cab6;
            color: var(--ink-strong);
        }

        .stButton > button {
            border-radius: 999px;
            border: 1px solid #1c468f;
            background: linear-gradient(180deg, #2559bc 0%, #19489f 100%);
            color: #ffffff;
            font-weight: 600;
            transition: transform 0.18s ease, box-shadow 0.18s ease;
        }

        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 20px rgba(20, 49, 112, 0.24);
        }

        .sidebar-title {
            font-family: "STZhongsong", "Songti SC", "Noto Serif CJK SC", serif;
            font-size: 1.2rem;
            color: #1f2d58;
            margin: 0.1rem 0 0.2rem 0;
        }

        .upload-note {
            margin-top: 0.15rem;
            color: #626d8b;
            font-size: 0.86rem;
        }

        footer {display: none !important;}

        @keyframes rise {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def run_agent_streamlit(prompt, max_iters=10):
    st.session_state.is_processing = True
    st.session_state.max_iters = max_iters
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()


def count_potential_tasks(files):
    """粗略估算文件中的日程条数。"""
    total_count = 0
    task_pattern = re.compile(r"\d{1,2}[:：]\d{2}|\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}")
    for file_obj in files:
        file_obj.seek(0)
        content = file_obj.read().decode("utf-8")
        file_obj.seek(0)
        total_count += len(task_pattern.findall(content))
    return total_count


init_session_state()
render_theme()

now = datetime.now()
sorted_schedules = get_sorted_schedules()
today_count = sum(
    1
    for item in sorted_schedules
    if item["dt"] != datetime.max and item["dt"].date() == now.date()
)
upcoming_count = sum(1 for item in sorted_schedules if item["dt"] != datetime.max and item["dt"] >= now)

st.markdown(
    f"""
    <section class="hero-card">
        <p class="hero-eyebrow">Personal Operations OS</p>
        <h1>智能日程助手 Agent</h1>
        <p class="hero-sub">
            把聊天指令与文档笔记自动转成结构化日程，让「记录、整理、执行」在一个页面里闭环。
        </p>
        <div class="hero-stats">
            <span class="hero-chip">总日程 {len(sorted_schedules)} 条</span>
            <span class="hero-chip">今日任务 {today_count} 条</span>
            <span class="hero-chip">待执行 {upcoming_count} 条</span>
            <span class="hero-chip">{now.strftime('%Y-%m-%d %H:%M')}</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("<p class='sidebar-title'>日程索引</p>", unsafe_allow_html=True)
    st.caption("支持按年 / 月 / 日折叠查看，快速删除单项。")
    summary_cols = st.columns(2)
    summary_cols[0].metric("今日", today_count)
    summary_cols[1].metric("待执行", upcoming_count)
    st.caption(f"系统时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    if not sorted_schedules:
        st.info("目前没有日程安排。")
    else:
        grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for item in sorted_schedules:
            if item["dt"] == datetime.max:
                grouped["未分类"]["-"]["-"].append(item)
            else:
                grouped[item["dt"].year][item["dt"].month][item["dt"].day].append(item)

        for year in sort_mixed_keys(grouped.keys(), reverse_int=True):
            is_current_year = isinstance(year, int) and year == now.year
            year_label = f"{year} 年" if isinstance(year, int) else str(year)
            with st.expander(f"📘 {year_label}", expanded=is_current_year):
                months = grouped[year]
                for month in sort_mixed_keys(months.keys()):
                    is_current_month = is_current_year and isinstance(month, int) and month == now.month
                    month_label = f"{month} 月" if isinstance(month, int) else str(month)
                    with st.expander(f"📁 {month_label}", expanded=is_current_month):
                        days = months[month]
                        for day in sort_mixed_keys(days.keys()):
                            is_today = (
                                is_current_month
                                and isinstance(day, int)
                                and day == now.day
                            )
                            day_label = f"{day} 日" if isinstance(day, int) else str(day)
                            with st.expander(f"🗂 {day_label}", expanded=is_today):
                                table_head = st.columns([0.26, 0.56, 0.18])
                                table_head[0].caption("**时间**")
                                table_head[1].caption("**任务**")
                                table_head[2].caption("**操作**")
                                for item in days[day]:
                                    row = st.columns([0.26, 0.56, 0.18])
                                    with row[0]:
                                        time_only = (
                                            item["dt"].strftime("%H:%M")
                                            if item["dt"] != datetime.max
                                            else "未知"
                                        )
                                        st.write(f"`{time_only}`")
                                    with row[1]:
                                        st.write(item["task"])
                                        st.caption(f"ID: {item['id']}")
                                    with row[2]:
                                        if st.button(
                                            "删除",
                                            key=f"del_{item['id']}_{day}",
                                            help="删除该日程",
                                        ):
                                            delete_schedule(item["id"])
                                            st.rerun()

    st.divider()
    if st.button("清空所有日程", type="primary", use_container_width=True):
        save_schedules([])
        st.rerun()

st.markdown("<p class='section-label'>Dialog Feed</p>", unsafe_allow_html=True)
history_container = st.container(height=520, border=False)
with history_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

st.markdown("<p class='section-label'>Document Sync</p>", unsafe_allow_html=True)
st.markdown(
    "<p class='upload-note'>上传 Markdown / TXT 文档，或在聊天中粘贴飞书文档链接，Agent 会自动提取并同步可识别的日程。</p>",
    unsafe_allow_html=True,
)

uploaded_files = st.file_uploader(
    "上传文件并同步日程",
    type=["md", "txt"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}",
    label_visibility="collapsed",
    disabled=st.session_state.is_processing,
)
analyze_btn = st.button(
    "开始分析并同步日程",
    use_container_width=True,
    disabled=st.session_state.is_processing or not uploaded_files,
)

user_input = st.chat_input(
    "输入指令（支持飞书文档链接），或上传文件分析...",
    disabled=st.session_state.is_processing,
)

if st.session_state.is_processing and st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    prompt = st.session_state.messages[-1]["content"]
    max_iters = st.session_state.max_iters

    context_messages = [
        {"role": "system", "content": get_system_prompt().format(tools_description=build_tools_description())}
    ]
    for message in st.session_state.messages[-10:-1]:
        context_messages.append(message)
    context_messages.append({"role": "user", "content": prompt})

    with history_container:
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            status_placeholder = st.status(f"Agent 正在处理任务 (最大迭代: {max_iters})...", expanded=True)
            full_response_text = ""

            for idx in range(max_iters):
                response = call_ollama(context_messages)
                full_response_text += response + "\n\n"
                context_messages.append({"role": "assistant", "content": response})
                response_placeholder.markdown(full_response_text)

                if "调用工具:" in response:
                    tool_lines = [line for line in response.split("\n") if "调用工具:" in line]
                    if not tool_lines:
                        break
                    tool_call_str = tool_lines[0].replace("调用工具:", "").strip()
                    status_placeholder.write(f"第 {idx + 1} 步: 执行工具 {tool_call_str}")
                    observation = execute_tool(tool_call_str)
                    status_placeholder.write(f"结果: {observation}")
                    context_messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
                elif "回复:" in response or "结论:" in response:
                    status_placeholder.update(label="任务处理完成", state="complete")
                    break
                else:
                    break

            st.session_state.messages.append({"role": "assistant", "content": full_response_text})

    st.session_state.is_processing = False
    if getattr(st.session_state, "pending_file_task", False):
        st.session_state.uploader_key += 1
        st.session_state.pending_file_task = False
    st.rerun()

if analyze_btn and uploaded_files and not st.session_state.is_processing:
    task_count = count_potential_tasks(uploaded_files)
    dynamic_max_iters = max(task_count + 3, 5)

    upload_cache_dir = UPLOADS_DIR
    os.makedirs(upload_cache_dir, exist_ok=True)

    saved_paths = []
    for file_obj in uploaded_files:
        save_path = os.path.abspath(os.path.join(upload_cache_dir, file_obj.name))
        with open(save_path, "wb") as buffer:
            buffer.write(file_obj.read())
        saved_paths.append(save_path)

    paths_str = "\n".join([f"- {path}" for path in saved_paths])
    st.session_state.pending_file_task = True
    run_agent_streamlit(
        f"请使用 read_document 工具读取以下路径的文件并记录其中的日程：\n\n{paths_str}",
        max_iters=dynamic_max_iters,
    )

if user_input and not st.session_state.is_processing:
    run_agent_streamlit(user_input, max_iters=10)
