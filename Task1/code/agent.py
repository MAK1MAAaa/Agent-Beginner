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

def get_system_prompt():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    
    time_context = {
        "full_now": now.strftime('%Y-%m-%d %H:%M:%S'),
        "weekday": now.strftime('%A'),
        "today": now.strftime('%Y-%m-%d'),
        "tomorrow": tomorrow.strftime('%Y-%m-%d'),
    }
    
    prompt = f"""你是一个专业、严谨的个人日程助手。
当前精确时间信息如下：
- 当前完整时间: {time_context['full_now']}
- 今天是: {time_context['weekday']} ({time_context['today']})
- 明天是: {time_context['tomorrow']}

你的任务是根据用户的输入管理日程。
你可以执行以下工具：
{{tools_description}}

核心原则：
1. **时间转换**：必须结合当前时间，将相对时间词汇转换为确切的 'YYYY-MM-DD HH:MM' 格式。
2. **ReAct 格式**：
   思考: <分析意图并提取具体的 time 和 task>
   调用工具: tool_name(key1="value1", key2="value2")
   (等待结果)
   思考: <判断是否需要下一步操作>
   回复: <给用户的最终回答>

示例：
调用工具: add_schedule(time="2024-12-01 10:00", task="周会")

注意：参数名必须匹配工具定义中的参数名（如 time, task, event_id, file_path）。不要使用“参数”作为键名。
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
    match = re.search(r"(\w+)\s*\((.*)\)", tool_call_str)
    if not match:
        return f"工具调用格式错误: '{tool_call_str}'"
    
    name, args_str = match.groups()
    kwargs = {}
    if args_str:
        # 提取键值对
        pairs = re.findall(r"(\w+)\s*=\s*['\"]?([^,'\"]*)['\"]?", args_str)
        for k, v in pairs:
            kwargs[k] = v.strip()

    print(f"  --> 执行工具: {name} (参数: {kwargs})")
    
    try:
        if name == "add_schedule":
            # 兼容性处理：如果模型依然用了错误的参数名
            if "time" not in kwargs and len(kwargs) > 0:
                return "错误：add_schedule 需要 'time' 和 'task' 参数，请检查调用格式。"
            return add_schedule(**kwargs)
        elif name == "list_schedules":
            return list_schedules()
        elif name == "delete_schedule":
            return delete_schedule(**kwargs)
        elif name == "read_document":
            return read_document(**kwargs)
        return f"未知工具: {name}"
    except TypeError as e:
        return f"工具调用参数错误: {str(e)}。请确保使用工具定义中指定的参数名。"

def run_agent(user_input):
    messages = [
        {"role": "system", "content": get_system_prompt().format(tools_description=build_tools_description())},
        {"role": "user", "content": user_input}
    ]
    
    for _ in range(5):
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
        else:
            break
