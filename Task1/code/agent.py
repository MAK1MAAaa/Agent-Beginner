import json
import requests
import os
import sys
import re
from datetime import datetime

# 确保 code 目录在 path 中
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

from schedule_manager import add_schedule, list_schedules, delete_schedule, read_document

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
        "name": "delete_schedule",
        "description": "删除指定的日程 ID",
        "parameters": {
            "event_id": "日程 ID"
        }
    },
    {
        "name": "read_document",
        "description": "读取目录下的 Markdown 或聊天记录文档",
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
1. 你的目的是将用户提供的信息转换为结构化的日程。
2. 调用工具后，你会得到执行结果（Observation），请根据结果决定下一步操作。
3. 如果调用工具返回错误（例如文件不存在），请尝试其他可能的方法或告知用户。
4. 调用工具时，参数值务必用引号包裹，例如: add_schedule(time="2024-12-01 10:00", task="任务名")
5. 每次只调用一个工具。
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
    # 增加正则表达式容错性，支持 key=value 以及 key="value"
    match = re.search(r"(\w+)\s*\((.*)\)", tool_call_str)
    if not match:
        return f"工具调用格式错误: '{tool_call_str}'。格式应为 tool_name(param1=val1, ...)"
    
    name, args_str = match.groups()
    kwargs = {}
    if args_str:
        # 支持复杂的参数提取，包括可能带有空格或特殊符号的值
        # 先寻找 key= 的模式，然后尝试提取之后的值直到下一个 key= 或末尾
        pairs = re.findall(r"(\w+)\s*=\s*['\"]?([^,'\"]*)['\"]?", args_str)
        for k, v in pairs:
            kwargs[k] = v.strip()

    print(f"  --> 执行工具: {name} (参数: {kwargs})")
    
    if name == "add_schedule":
        return add_schedule(**kwargs)
    elif name == "list_schedules":
        return list_schedules()
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
    
    for _ in range(5):
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
            break

if __name__ == "__main__":
    test_text = "帮我读取 note.md 里的日程"
    run_agent(test_text)
