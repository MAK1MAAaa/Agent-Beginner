import streamlit as st
import os
import sys
import pandas as pd
from datetime import datetime
import re

# 确保 code 目录在 path 中，方便导入 agent 和 schedule_manager
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

from agent import SYSTEM_PROMPT, build_tools_description, call_ollama, execute_tool
from schedule_manager import list_schedules, load_schedules, delete_schedule, save_schedules

# 设置页面
st.set_page_config(page_title="智能日程助手 Agent", layout="wide")
st.title("📅 智能日程助手 Agent")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 侧边栏：实时日程管理 ---
with st.sidebar:
    st.header("📋 当前日程表")
    schedules = load_schedules()
    if not schedules:
        st.info("目前没有日程安排。")
    else:
        df = pd.DataFrame(schedules)
        # 修复 Streamlit 警告：使用 width='stretch' 代替 use_container_width=True
        st.dataframe(df, width='stretch', hide_index=True)
        
        st.subheader("快速操作")
        event_id_to_delete = st.text_input("输入要删除的日程 ID", placeholder="例如: 1")
        if st.button("❌ 确认删除", width='stretch'):
            if event_id_to_delete:
                res = delete_schedule(event_id_to_delete)
                st.success(res)
                st.rerun()
            else:
                st.warning("请输入有效的 ID")

    st.divider()
    if st.button("🗑️ 清空所有日程", type="primary", width='stretch'):
        save_schedules([])
        st.success("所有日程已清空")
        st.rerun()

# --- 主界面布局 ---

# 1. 文件上传移动到输入框上方
st.markdown("### 📥 导入内容")
uploaded_file = st.file_uploader("上传 Markdown 笔记或聊天记录 (md, txt)", type=["md", "txt"])

# 2. 对话显示区域
st.subheader("🤖 Agent 对话与执行")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 3. 输入逻辑
user_input = st.chat_input("在这里输入指令...")

# 逻辑触发：分析上传的文件 (将内容直接放入 Prompt，避免 Agent 反复调用 read_document 失败)
if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    if st.button("🚀 分析并记录上传内容", width='stretch'):
        prompt = f"请分析以下文件内容并将其中的日程添加到我的日程表中。文件内容如下：\n\n```\n{file_content}\n```"
        user_input = prompt

def run_agent_streamlit(prompt):
    # 构建当前上下文消息
    context_messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools_description=build_tools_description())},
    ]
    # 添加历史（保持简洁）
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
        
        # ReAct 循环
        for i in range(5):
            response = call_ollama(context_messages)
            full_response_text += response + "\n\n"
            context_messages.append({"role": "assistant", "content": response})
            
            # 实时更新回复显示
            response_container.markdown(full_response_text)
            
            # 解析工具调用
            if "调用工具:" in response:
                tool_lines = [l for l in response.split('\n') if "调用工具:" in l]
                if tool_lines:
                    tool_call_str = tool_lines[0].replace("调用工具:", "").strip()
                    status_placeholder.write(f"第 {i+1} 步: 🔧 执行工具: {tool_call_str}")
                    
                    observation = execute_tool(tool_call_str)
                    status_placeholder.write(f"✅ 结果: {observation}")
                    
                    # 将结果反馈给模型
                    context_messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
                    
                    # 特殊处理：如果是 read_document 且成功，模型应该能看到内容了
                    # 如果还是循环，通常是因为模型没理解 Observation
                else:
                    break
            elif "回复:" in response or "结论:" in response:
                status_placeholder.update(label="任务处理完成", state="complete")
                break
            else:
                # 如果没有明显的工具调用或回复标识，但模型输出了内容，我们也暂时停止或继续观察
                if i == 4: # 最后一次循环
                     status_placeholder.update(label="已达到最大尝试次数", state="complete")
                continue
        
        st.session_state.messages.append({"role": "assistant", "content": full_response_text})
        st.rerun()

if user_input:
    run_agent_streamlit(user_input)
