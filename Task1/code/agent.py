import json
import requests
import os
import sys

# 确保 code 目录在 path 中
sys.path.append(os.path.dirname(__file__))

from schedule_manager import add_schedule, list_schedules, update_schedule, delete_schedule

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
    }
]

SYSTEM_PROMPT = """你是一个个人日程助手。你可以通过工具来管理用户的日程。
你可以执行以下工具：
{tools_description}

回复格式：
思考: <思考过程>
调用工具: <工具名>(<参数1>=<值1>, <参数2>=<值2>)
或者回复结果给用户。

当用户提供一段文本（如聊天记录或笔记）时，请识别其中包含的日程信息，并调用相应工具。
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
    response = requests.post(OLLAMA_URL, json=payload)
    return response.json()["message"]["content"]

def execute_tool(tool_call_str):
    import re
    match = re.match(r"(\w+)\((.*)\)", tool_call_str)
    if not match:
        return "工具调用格式错误"
    
    name, args_str = match.groups()
    kwargs = {}
    if args_str:
        # 更健壮的正则，支持双引号和单引号
        pairs = re.findall(r"(\w+)=['\"]?([^,'\"]+)['\"]?", args_str)
        for k, v in pairs:
            kwargs[k] = v

    if name == "add_schedule":
        return add_schedule(**kwargs)
    elif name == "list_schedules":
        return list_schedules()
    elif name == "update_schedule":
        return update_schedule(**kwargs)
    return f"未知工具: {name}"

def run_agent(user_input):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools_description=build_tools_description())},
        {"role": "user", "content": user_input}
    ]
    
    print(f"User: {user_input}")
    
    for _ in range(3):
        response = call_ollama(messages)
        print(f"Assistant: {response}")
        messages.append({"role": "assistant", "content": response})
        
        if "调用工具:" in response:
            tool_call_line = [line for line in response.split('\n') if "调用工具:" in line][0]
            tool_call_str = tool_call_line.replace("调用工具:", "").strip()
            
            observation = execute_tool(tool_call_str)
            print(f"Observation: {observation}")
            messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
        else:
            break

if __name__ == "__main__":
    test_text = "小明在群里说：明天下午两点记得在会议室开周会。帮我记一下。"
    run_agent(test_text)
