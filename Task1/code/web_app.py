import streamlit as st
import os
import sys
from agent import run_agent, SYSTEM_PROMPT, build_tools_description, call_ollama, execute_tool

# 设置页面
st.set_page_config(page_title="个人日程助手 Agent", layout="wide")
st.title("📅 个人日程助手 Agent (ReAct)")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

# 侧边栏：显示当前日程
with st.sidebar:
    st.header("📋 当前日程列表")
    from schedule_manager import list_schedules
    st.text(list_schedules())
    
    st.divider()
    if st.button("🗑️ 清空日程"):
        from schedule_manager import save_schedules
        save_schedules([])
        st.success("日程已清空")
        st.rerun()

# 用户输入区域
st.subheader("🤖 与 Agent 对话")
user_input = st.chat_input("输入指令，例如：帮我记一下明天下午三点开会")

# 处理文件上传
uploaded_file = st.file_uploader("📂 或者上传一个 Markdown 笔记/聊天记录文件", type=["md", "txt"])
if uploaded_file is not None:
    content = uploaded_file.read().decode("utf-8")
    if st.button("🚀 分析上传的文件"):
        user_input = f"请读取并分析以下内容中的日程，并帮我记录下来：\n\n{content}"

# Agent 运行逻辑 (Streamlit 版)
def run_agent_streamlit(prompt):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools_description=build_tools_description())},
        {"role": "user", "content": prompt}
    ]
    
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        thought_placeholder = st.empty()
        status_placeholder = st.status("Agent 正在思考...")
        
        full_response = ""
        for _ in range(5):
            response = call_ollama(messages)
            full_response += response + "\n"
            messages.append({"role": "assistant", "content": response})
            
            # 在 UI 上展示思考过程
            thought_placeholder.markdown(full_response)
            
            if "调用工具:" in response:
                import re
                tool_call_line = [line for line in response.split('\n') if "调用工具:" in line][0]
                tool_call_str = tool_call_line.replace("调用工具:", "").strip()
                
                status_placeholder.write(f"正在执行工具: {tool_call_str}")
                observation = execute_tool(tool_call_str)
                status_placeholder.write(f"工具返回结果: {observation}")
                
                messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
            elif "回复:" in response:
                status_placeholder.update(label="任务完成", state="complete")
                break
            else:
                status_placeholder.update(label="模型回复格式不规范", state="error")
                break
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})

if user_input:
    run_agent_streamlit(user_input)

# 显示历史消息
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])
