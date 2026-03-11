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
from schedule_manager import list_schedules, load_schedules, delete_schedule, save_schedules

# 设置页面
st.set_page_config(page_title="智能日程助手 Agent", layout="wide")
st.title("📅 智能日程助手 Agent")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 辅助函数：解析与分组日程 ---
def get_sorted_schedules():
    schedules = load_schedules()
    parsed_data = []
    for s in schedules:
        try:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(s['time'], fmt)
                    break
                except:
                    continue
            if not dt:
                dt = datetime.max
        except Exception:
            dt = datetime.max
        
        parsed_data.append({
            "id": s.get("id"),
            "time_str": s.get("time"),
            "task": s.get("task"),
            "dt": dt
        })
    
    parsed_data.sort(key=lambda x: (x['dt'], x['id']))
    return parsed_data

# --- 侧边栏：全层级折叠日程表 ---
with st.sidebar:
    st.header("📋 我的日程库")
    
    now = datetime.now()
    st.caption(f"🕒 当前系统时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    sorted_schedules = get_sorted_schedules()
    
    if not sorted_schedules:
        st.info("目前没有日程安排。")
    else:
        # 按 年 -> 月 -> 日 分组
        grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for s in sorted_schedules:
            if s['dt'] == datetime.max:
                grouped["未分类"]["-"]["-"].append(s)
            else:
                grouped[s['dt'].year][s['dt'].month][s['dt'].day].append(s)

        # 渲染层级折叠目录
        for year in sorted(grouped.keys(), reverse=True if isinstance(grouped.keys(), int) else False):
            # 默认展开当前年份
            is_current_year = (year == now.year)
            with st.expander(f"📅 {year} 年", expanded=is_current_year):
                months = grouped[year]
                for month in sorted(months.keys()):
                    # 默认展开当前月份
                    is_current_month = (is_current_year and month == now.month)
                    with st.expander(f"🗓️ {month} 月", expanded=is_current_month):
                        days = months[month]
                        for day in sorted(days.keys()):
                            # 默认展开今天
                            is_today = (is_current_month and day == now.day)
                            with st.expander(f"📍 {day} 日", expanded=is_today):
                                # 表头
                                cols_h = st.columns([0.25, 0.55, 0.2])
                                cols_h[0].caption("**时间**")
                                cols_h[1].caption("**任务**")
                                cols_h[2].caption("**操作**")
                                
                                for item in days[day]:
                                    cols = st.columns([0.25, 0.55, 0.2])
                                    with cols[0]:
                                        time_only = item['dt'].strftime('%H:%M') if item['dt'] != datetime.max else "未知"
                                        st.write(f"`{time_only}`")
                                    with cols[1]:
                                        st.write(item['task'])
                                    with cols[2]:
                                        if st.button("🗑️", key=f"del_{item['id']}", help="删除"):
                                            delete_schedule(item['id'])
                                            st.rerun()
        
    st.divider()
    if st.button("🗑️ 清空所有日程", type="primary", width='stretch'):
        save_schedules([])
        st.success("日程已清空")
        st.rerun()

# --- 主界面布局 ---
st.markdown("### 📥 导入内容")
uploaded_file = st.file_uploader("上传 Markdown 笔记或聊天记录 (md, txt)", type=["md", "txt"])

st.subheader("🤖 Agent 对话与执行")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("在这里输入指令...")

if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    if st.button("🚀 分析并记录上传内容", width='stretch'):
        prompt = f"请分析以下文件内容并将其中的日程添加到我的日程表中。内容如下：\n\n```\n{file_content}\n```"
        user_input = prompt

def run_agent_streamlit(prompt):
    context_messages = [
        {"role": "system", "content": get_system_prompt().format(tools_description=build_tools_description())},
    ]
    for msg in st.session_state.messages[-3:]:
        context_messages.append(msg)
    context_messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        response_container = st.empty()
        status_placeholder = st.status("Agent 正在处理...", expanded=True)
        
        full_response_text = ""
        for i in range(5):
            response = call_ollama(context_messages)
            full_response_text += response + "\n\n"
            context_messages.append({"role": "assistant", "content": response})
            response_container.markdown(full_response_text)
            
            if "调用工具:" in response:
                tool_lines = [l for l in response.split('\n') if "调用工具:" in l]
                if tool_lines:
                    tool_call_str = tool_lines[0].replace("调用工具:", "").strip()
                    status_placeholder.write(f"第 {i+1} 步: 🔧 执行工具: {tool_call_str}")
                    observation = execute_tool(tool_call_str)
                    status_placeholder.write(f"✅ 结果: {observation}")
                    context_messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
                else:
                    break
            elif "回复:" in response or "结论:" in response:
                status_placeholder.update(label="任务处理完成", state="complete")
                break
            else:
                if i == 4:
                     status_placeholder.update(label="已达到最大尝试次数", state="complete")
                continue
        
        st.session_state.messages.append({"role": "assistant", "content": full_response_text})
        st.rerun()

if user_input:
    run_agent_streamlit(user_input)
