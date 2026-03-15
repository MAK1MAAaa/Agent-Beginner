import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

# 确保 code 目录在 path 中
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.append(current_dir)

from schedule_manager import (
    add_schedule_with_date,
    add_schedule,
    delete_schedule,
    list_schedules,
    read_document,
    read_feishu_doc,
    rename_schedule,
    reschedule_schedule,
    update_schedule,
)


def load_local_env_file():
    """从 code/.env 加载环境变量（不覆盖系统已存在变量）。"""
    env_path = os.path.join(current_dir, ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


load_local_env_file()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
MODEL_TIMEOUT_SECONDS = int(os.getenv("MODEL_TIMEOUT_SECONDS", "30"))
ENABLE_FALLBACK = os.getenv("ENABLE_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}

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
        "name": "add_schedule_with_date",
        "description": "新增日程的便捷工具：当用户给出日期和时分时使用。",
        "parameters": {
            "date": "日期，格式 YYYY-MM-DD",
            "clock_time": "时间，格式 HH:MM",
            "task": "任务内容"
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
        "name": "read_feishu_doc",
        "description": "读取飞书文档正文。支持传 doc_url 或 doc_token，读取后请解析并按需新增/修改日程。",
        "parameters": {
            "doc_url": "飞书文档链接（可选）",
            "doc_token": "飞书文档 token（可选）"
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
    },
    {
        "name": "update_schedule",
        "description": "按 ID 修改日程，可同时修改时间与任务描述。",
        "parameters": {
            "event_id": "日程 ID",
            "new_time": "新的时间（可选）",
            "new_task": "新的任务描述（可选）"
        }
    },
    {
        "name": "reschedule_schedule",
        "description": "按 ID 只修改日程时间。",
        "parameters": {
            "event_id": "日程 ID",
            "new_time": "新的时间"
        }
    },
    {
        "name": "rename_schedule",
        "description": "按 ID 只修改任务描述。",
        "parameters": {
            "event_id": "日程 ID",
            "new_task": "新的任务描述"
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
1. **读取与解析**:
   - 如果用户提供的是本地文件路径或上传文件，先调用 `read_document`。
   - 如果用户提供的是飞书文档链接，先调用 `read_feishu_doc`。
2. **新增日程操作**: 识别到新增需求时，使用 `add_schedule` 逐条添加。
   - 如果用户给的是“日期 + 时分”拆分信息，可使用 `add_schedule_with_date`。
3. **修改日程操作**: 用户要求“改时间/改描述/调整安排”时，优先使用 `update_schedule`、`reschedule_schedule` 或 `rename_schedule`。
4. **先查后改**: 如果缺少 ID 或目标不明确，先调用 `list_schedules` 获取上下文，再执行修改工具。
5. **单步执行**: 每一轮回复只能包含**一个**“调用工具:”指令。
6. **回复**: 完成所有新增/修改后，使用“回复:”告知用户结果。

回复格式：
思考: <分析当前状态，确定下一步工具动作>
调用工具: <工具名>(<参数>=<值>)
"""
    return prompt

def build_tools_description():
    desc = ""
    for t in TOOLS:
        desc += f"- {t['name']}: {t['description']}, 参数: {t['parameters']}\n"
    return desc


def collect_fallback_configs():
    """收集备用 API 配置，支持最多 3 组 OpenAI 兼容接口。"""
    configs = []
    slots = [
        ("FALLBACK_API_BASE_URL", "FALLBACK_API_KEY", "FALLBACK_API_MODEL", "FALLBACK_API_NAME"),
        ("FALLBACK2_API_BASE_URL", "FALLBACK2_API_KEY", "FALLBACK2_API_MODEL", "FALLBACK2_API_NAME"),
        ("FALLBACK3_API_BASE_URL", "FALLBACK3_API_KEY", "FALLBACK3_API_MODEL", "FALLBACK3_API_NAME"),
    ]

    for idx, (base_key, token_key, model_key, name_key) in enumerate(slots, start=1):
        base_url = os.getenv(base_key, "").strip()
        api_key = os.getenv(token_key, "").strip()
        model = os.getenv(model_key, "").strip()
        name = os.getenv(name_key, "").strip() or f"Fallback-{idx}"
        if base_url and api_key and model:
            configs.append(
                {
                    "name": name,
                    "base_url": base_url.rstrip("/"),
                    "api_key": api_key,
                    "model": model,
                }
            )

    return configs


def call_ollama_local(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=MODEL_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def call_openai_compatible(messages, config):
    endpoint = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": messages,
        "stream": False,
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=MODEL_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def call_ollama(messages):
    """优先调用本地 Ollama；不可用时自动切到备用 API。"""
    error_messages = []

    try:
        return call_ollama_local(messages)
    except Exception as e:
        error_messages.append(f"Ollama 不可用: {str(e)}")

    if not ENABLE_FALLBACK:
        return f"错误：调用 Ollama 失败，且未启用备用 API。{error_messages[0]}"

    fallback_configs = collect_fallback_configs()
    if not fallback_configs:
        return (
            "错误：本地 Ollama 不可用，且未配置备用 API。"
            "请在 Task1/code/.env 中填写 FALLBACK_API_BASE_URL/FALLBACK_API_KEY/FALLBACK_API_MODEL。"
        )

    for config in fallback_configs:
        try:
            return call_openai_compatible(messages, config)
        except Exception as e:
            error_messages.append(f"{config['name']} 调用失败: {str(e)}")

    return "错误：本地与备用模型均调用失败。\n" + "\n".join(error_messages)

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
    elif name == "add_schedule_with_date":
        return add_schedule_with_date(**kwargs)
    elif name == "list_schedules":
        return list_schedules()
    elif name == "delete_schedule":
        return delete_schedule(**kwargs)
    elif name == "read_document":
        return read_document(**kwargs)
    elif name == "read_feishu_doc":
        return read_feishu_doc(**kwargs)
    elif name == "update_schedule":
        return update_schedule(**kwargs)
    elif name == "reschedule_schedule":
        return reschedule_schedule(**kwargs)
    elif name == "rename_schedule":
        return rename_schedule(**kwargs)
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
