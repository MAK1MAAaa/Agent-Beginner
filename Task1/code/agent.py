import json
import requests
import os
import sys
import re
from datetime import datetime, timedelta

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
        "description": "【核心工具】将识别到的具体日程（时间、任务）添加到数据库中。请务必使用此工具来记录新日程。",
        "parameters": {
            "time": "确切的时间格式 'YYYY-MM-DD HH:MM'",
            "task": "具体的任务内容"
        }
    },
    {
        "name": "read_document",
        "description": "读取指定路径的文档内容。读取后，请立即分析内容并使用 add_schedule 逐条记录其中的日程。",
        "parameters": {
            "file_path": "文件的绝对路径"
        }
    },
    {
        "name": "list_schedules",
        "description": "仅用于查看当前已保存的所有日程。不要在需要『添加』或『记录』日程时调用此工具。",
        "parameters": {}
    },
    {
        "name": "delete_schedule",
        "description": "根据 ID 删除指定的日程。",
        "parameters": {
            "event_id": "日程 ID"
        }
    }
]

def get_system_prompt():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    
    time_context = {
        "full_now": now.strftime('%Y-%m-%d %H:%M:%S'),
        "weekday": now.strftime('%A'),
        "today": now.strftime('%Y-%m-%d'),
        "tomorrow": tomorrow.strftime('%Y-%m-%d'),
    }
    
    prompt = f"""你是一个高效、准确的个人日程管理专家。
当前系统环境:
- 当前时间: {time_context['full_now']}
- 今天: {time_context['today']} ({time_context['weekday']})

你拥有的工具及其说明：
{{tools_description}}

工作流程 (非常重要)：
1. **读取与解析**: 如果用户提供了一个文件路径或上传了文件，第一步必须是调用 `read_document`。
2. **记录操作**: 读取文件内容后，你的唯一目标是调用 `add_schedule` 将其中的日程**逐条添加**。
3. **禁止无效循环**: 除非用户明确要求“列出”或“查看”，否则严禁调用 `list_schedules`。特别是在读取文件后，你的下一步动作必须是解析并添加日程，而不是查看日程。
4. **单步执行**: 每一轮回复只能包含**一个**“调用工具:”指令。
5. **多日程处理**: 
   - 识别出日程 A, B, C...
   - 步骤1: 调用工具: add_schedule(time="...", task="A")
   - 等待 Observation 成功后
   - 步骤2: 调用工具: add_schedule(time="...", task="B")
   - 依此类推，直到全部添加。
6. **回复**: 当所有识别到的日程都添加完成后，使用“回复:”告知用户。

回复格式：
思考: <分析当前状态，确定下一个要添加的日程>
调用工具: <工具名>(<参数>=<值>)
"""
    return prompt

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
    if tool_call_str.count("调用工具:") > 1:
        return "错误：一次只能调用一个工具，请分步骤执行。"

    # 使用更健壮的正则，支持 Windows 路径中的反斜杠
    match = re.search(r"(\w+)\s*\((.*)\)", tool_call_str)
    if not match:
        return f"工具调用格式错误: '{tool_call_str}'"
    
    name, args_str = match.groups()
    kwargs = {}
    if args_str:
        # 修正正则，以便更好地处理路径和引号
        pairs = re.findall(r"(\w+)\s*=\s*['\"]?(.*?)['\"]?(?:,|$)", args_str)
        for k, v in pairs:
            kwargs[k] = v.strip().strip("'\"")

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
        {"role": "system", "content": get_system_prompt().format(tools_description=build_tools_description())},
        {"role": "user", "content": user_input}
    ]
    for _ in range(20):
        response = call_ollama(messages)
        messages.append({"role": "assistant", "content": response})
        if "调用工具:" in response:
            lines = response.split('\n')
            tool_call_line = [line for line in lines if "调用工具:" in line][0]
            tool_call_str = tool_call_line.replace("调用工具:", "").strip()
            observation = execute_tool(tool_call_str)
            messages.append({"role": "user", "content": f"工具执行结果: {observation}"})
        elif "回复:" in response:
            break
        else: break
