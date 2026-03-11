import json
import requests
import os
import sys
import re
from datetime import datetime

# 确保 code 目录在 path 中
sys.path.append(os.path.dirname(__file__))

from schedule_manager import add_schedule, list_schedules, update_schedule, delete_schedule, read_document

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-coder:7b"

TOOLS = [
    {
        "name": "add_schedule",
        "description": "添加新的日程安排",
        "parameters": {
            "time": "时间字符串 (例如: '2024-12-01 10:00')",
            "task": "具体的任务内容"
        }
    },
    {
        "name": "list_schedules",
        "description": "查看当前所有的日程列表",
        "parameters": {}
    },
    {
        "name": "update_schedule",
        "description": "根据 ID 修改已有的日程内容或时间",
        "parameters": {
            "event_id": "日程 ID",
            "time": "新的时间 (可选)",
            "task": "新的任务内容 (可选)"
        }
    },
    {
        "name": "delete_schedule",
        "description": "删除指定的日程 ID",
        "parameters": {
            "event_id": "日程 ID"
        }
    },
    {
        "name": "read_document",
        "description": "读取 test 目录下的 Markdown 或聊天记录文档",
        "parameters": {
            "file_path": "文件名，例如: 'note.md' 或 'chat.txt'"
        }
    }
]

SYSTEM_PROMPT = f"""你是一个个人日程助手。当前时间是: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}。
你可以执行以下工具来管理用户的日程：
{{tools_description}}

回复格式要求：
思考: <你的思考过程，包括分析用户意图、判断需要调用哪个工具以及参数提取>
调用工具: <工具名>(<参数1>=<值1>, <参数2>=<值2>)
或者（当任务完成或需要用户反馈时）：
回复: <你对用户的回复>

注意：
1. 如果用户让你从某个文件中提取日程，请先调用 `read_document`。
2. 调用工具后，你会得到执行结果（Observation），请根据结果决定下一步操作（是继续调用工具还是回复用户）。
3. 务必根据当前时间准确计算“明天”、“下周”等相对时间。
"""

def build_tools_description():
    desc = ""
    for t in TOOLS:
        desc += f"- {t['name']}: {t['description']}, 参数: {t['parameters']}\n"
    return desc

def call_ollama(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        return response.json()["message"]["content"]
    except Exception as e:
        return f"错误：调用 Ollama 失败: {str(e)}"

def execute_tool(tool_call_str):
    match = re.search(r"(\w+)\((.*)\)", tool_call_str)
    if not match:
        return "工具调用格式错误"
    
    name, args_str = match.groups()
    kwargs = {}
    if args_str:
        # 支持 key=value, key="value", key='value'
        pairs = re.findall(r"(\w+)\s*=\s*['\"]?([^,'\"]*)['\"]?", args_str)
        for k, v in pairs:
            kwargs[k] = v.strip()

    print(f"  --> 执行工具: {name} (参数: {kwargs})")
    
    if name == "add_schedule":
        return add_schedule(**kwargs)
    elif name == "list_schedules":
        return list_schedules()
    elif name == "update_schedule":
        return update_schedule(**kwargs)
    elif name == "delete_schedule":
        return delete_schedule(**kwargs)
    elif name == "read_document":
        return read_document(**kwargs)
    return f"未知工具: {name}"

def run_agent(user_input):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools_description=build_tools_description())},
        {"role": "user", "content": user_input}
    ]
    
    print(f"User: {user_input}")
    
    for _ in range(5): # 增加迭代次数以支持复杂任务
        response = call_ollama(messages)
        print(f"Assistant:\n{response}")
        messages.append({"role": "assistant", "content": response})
        
        if "调用工具:" in response:
            tool_call_line = [line for line in response.split('\n') if "调用工具:" in line][0]
            tool_call_str = tool_call_line.replace("调用工具:", "").strip()
            
            observation = execute_tool(tool_call_str)
            print(f"Observation: {observation}")
            messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
        elif "回复:" in response:
            break
        else:
            # 如果模型没有按格式回复，也跳出
            break

if __name__ == "__main__":
    # 可以通过交互模式运行，或者运行特定测试
    if len(sys.argv) > 1:
        run_agent(" ".join(sys.argv[1:]))
    else:
        # 默认演示
        print("--- 演示 1: 提取日程 ---")
        run_agent("我刚才在 note.md 记了一些日程，帮我同步到日程表里。")
