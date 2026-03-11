import streamlit as st
import os
import sys
import pandas as pd
from datetime import datetime
import re
from collections import defaultdict

# 确保 code 目录在 path 中
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

from agent import get_system_prompt, build_tools_description, call_ollama, execute_tool
from schedule_manager import list_schedules, load_schedules, delete_schedule, save_schedules, TEST_DIR

# 设置页面
st.set_page_config(page_title="智能日程助手 Agent", layout="wide")

# --- 1. CSS 恢复与优化 ---
st.markdown("""
    <style>
    .main .block-container {
        padding-bottom: 220px !important;
    }
    footer {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "max_iters" not in st.session_state:
    st.session_state.max_iters = 10

# --- 2. 固定上边栏 (Header) ---
st.title("📅 智能日程助手 Agent")
st.divider()

# --- 3. 侧边栏：三级全层级折叠日程表 ---
with st.sidebar:
    st.header("📋 我的日程库")
    now = datetime.now()
    st.caption(f"🕒 当前系统时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def get_sorted_schedules():
        schedules = load_schedules()
        parsed_data = []
        for s in schedules:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(s['time'], fmt)
                    break
                except: continue
            if not dt: dt = datetime.max
            parsed_data.append({"id": str(s.get("id")), "time_str": s.get("time"), "task": s.get("task"), "dt": dt})
        parsed_data.sort(key=lambda x: (x['dt'], x['id']))
        return parsed_data

    sorted_schedules = get_sorted_schedules()
    if not sorted_schedules:
        st.info("目前没有日程安排。")
    else:
        grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for s in sorted_schedules:
            if s['dt'] == datetime.max: grouped["未分类"]["-"]["-"].append(s)
            else: grouped[s['dt'].year][s['dt'].month][s['dt'].day].append(s)

        for year in sorted(grouped.keys(), reverse=True if isinstance(grouped.keys(), int) else False):
            is_current_year = (year == now.year)
            with st.expander(f"📅 {year} 年", expanded=is_current_year):
                months = grouped[year]
                for month in sorted(months.keys()):
                    is_current_month = (is_current_year and month == now.month)
                    with st.expander(f"🗓️ {month} 月", expanded=is_current_month):
                        days = months[month]
                        for day in sorted(days.keys()):
                            is_today = (is_current_month and day == now.day)
                            with st.expander(f"📍 {day} 日", expanded=is_today):
                                cols_h = st.columns([0.2, 0.6, 0.2])
                                cols_h[0].caption("**时间**")
                                cols_h[1].caption("**任务**")
                                cols_h[2].caption("**操作**")
                                for item in days[day]:
                                    cols = st.columns([0.2, 0.6, 0.2])
                                    with cols[0]:
                                        time_only = item['dt'].strftime('%H:%M') if item['dt'] != datetime.max else "未知"
                                        st.write(f"`{time_only}`")
                                    with cols[1]:
                                        st.write(f"{item['task']}")
                                        st.caption(f"ID: {item['id']}")
                                    with cols[2]:
                                        if st.button("🗑️", key=f"del_{item['id']}", help="删除"):
                                            delete_schedule(item['id'])
                                            st.rerun()
    st.divider()
    if st.button("🗑️ 清空所有日程", type="primary", width='stretch'):
        save_schedules([])
        st.rerun()

# --- 4. 中间对话历史 (可滚动) ---
history_container = st.container(height=500, border=False)
with history_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# --- 5. 底部功能区 ---
footer_area = st.container()
with footer_area:
    st.divider()
    uploaded_files = st.file_uploader(
        "上传文件并同步日程", 
        type=["md", "txt"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}",
        label_visibility="collapsed",
        disabled=st.session_state.is_processing
    )
    analyze_btn = st.button(
        "🚀 开始分析并同步日程", 
        width='stretch', 
        disabled=st.session_state.is_processing or not uploaded_files
    )

user_input = st.chat_input(
    "输入指令，或上传文件分析...", 
    disabled=st.session_state.is_processing
)

# --- 核心业务逻辑 ---

def run_agent_streamlit(prompt, max_iters=10):
    st.session_state.is_processing = True
    st.session_state.max_iters = max_iters
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

if st.session_state.is_processing:
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        prompt = st.session_state.messages[-1]["content"]
        max_iters = st.session_state.max_iters
        
        context_messages = [
            {"role": "system", "content": get_system_prompt().format(tools_description=build_tools_description())},
        ]
        for msg in st.session_state.messages[-10:-1]:
            context_messages.append(msg)
        context_messages.append({"role": "user", "content": prompt})

        with history_container:
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                status_placeholder = st.status(f"Agent 正在处理任务 (最大迭代: {max_iters})...", expanded=True)
                full_response_text = ""
                
                for i in range(max_iters):
                    response = call_ollama(context_messages)
                    full_response_text += response + "\n\n"
                    context_messages.append({"role": "assistant", "content": response})
                    response_placeholder.markdown(full_response_text)
                    
                    if "调用工具:" in response:
                        tool_lines = [l for l in response.split('\n') if "调用工具:" in l]
                        if tool_lines:
                            tool_call_str = tool_lines[0].replace("调用工具:", "").strip()
                            status_placeholder.write(f"第 {i+1} 步: 🔧 执行工具: {tool_call_str}")
                            observation = execute_tool(tool_call_str)
                            status_placeholder.write(f"✅ 结果: {observation}")
                            context_messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
                        else: break
                    elif "回复:" in response or "结论:" in response:
                        status_placeholder.update(label="任务处理完成", state="complete")
                        break
                    else: break
                st.session_state.messages.append({"role": "assistant", "content": full_response_text})
        
        st.session_state.is_processing = False
        if getattr(st.session_state, 'pending_file_task', False):
            st.session_state.uploader_key += 1
            st.session_state.pending_file_task = False
        st.rerun()

def count_potential_tasks(files):
    """粗略估算文件中的日程条数"""
    total_count = 0
    # 匹配时间格式如 "10:00" 或 "03月12日" 或 "2024-12-01"
    task_pattern = re.compile(r'\d{1,2}[:：]\d{2}|\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}')
    for f in files:
        # 指针回位
        f.seek(0)
        content = f.read().decode("utf-8")
        f.seek(0) # 再次回位供后续保存
        matches = task_pattern.findall(content)
        total_count += len(matches)
    return total_count

if analyze_btn and uploaded_files and not st.session_state.is_processing:
    # 估算总条数
    task_count = count_potential_tasks(uploaded_files)
    # 根据你的要求：总条数 + 3 作为迭代次数
    dynamic_max_iters = task_count + 3
    # 至少保证有基本的迭代次数
    dynamic_max_iters = max(dynamic_max_iters, 5)
    
    upload_cache_dir = os.path.join(TEST_DIR, "uploads")
    os.makedirs(upload_cache_dir, exist_ok=True)
    
    saved_paths = []
    for f in uploaded_files:
        save_path = os.path.abspath(os.path.join(upload_cache_dir, f.name))
        with open(save_path, "wb") as buffer:
            buffer.write(f.read())
        saved_paths.append(save_path)
    
    paths_str = "\n".join([f"- {p}" for p in saved_paths])
    st.session_state.pending_file_task = True
    run_agent_streamlit(
        f"请使用 read_document 工具读取以下路径的文件并记录其中的日程：\n\n{paths_str}",
        max_iters=dynamic_max_iters
    )

if user_input and not st.session_state.is_processing:
    run_agent_streamlit(user_input, max_iters=10) # 普通输入默认 10 次
