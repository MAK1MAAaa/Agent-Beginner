import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse

import requests

# 加载 code/.env，方便独立调用本模块时也能读到飞书配置
CURRENT_DIR = os.path.dirname(__file__)

def load_local_env_file():
    env_path = os.path.join(CURRENT_DIR, ".env")
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

# 将数据文件存放在 ../data/ 目录下
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test"))
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
DOWNLOADS_DIR = r"C:\Users\MAK1MA\Downloads" # 外部下载目录
DB_FILE = os.path.join(DATA_DIR, "schedules.json")

def load_schedules():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_schedules(schedules):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

def normalize_time_str(time_str):
    try:
        dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(time_str.strip(), fmt)
                break
            except: continue
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M")
    except:
        pass
    return time_str.strip()

def generate_base_id(target_time_str):
    now = datetime.now()
    now_str = now.strftime("%y%m%d%H%M")
    try:
        target_dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                target_dt = datetime.strptime(target_time_str.strip(), fmt)
                break
            except: continue
        target_str = target_dt.strftime("%y%m%d%H%M") if target_dt else "0000000000"
    except:
        target_str = "0000000000"
    return f"{now_str}{target_str}"

def add_schedule(time, task):
    schedules = load_schedules()
    normalized_time = normalize_time_str(time)
    base_id = generate_base_id(normalized_time)
    final_id = None
    for i in range(1, 100):
        suffix = f"{i:02d}"
        candidate_id = f"{base_id}{suffix}"
        if not any(str(s.get("id")) == str(candidate_id) for s in schedules):
            final_id = str(candidate_id)
            break
    if not final_id:
        return f"错误：时间段 {normalized_time} 的日程容量已满 (99条上限)。无法添加: {task}"
    event = {"id": final_id, "time": normalized_time, "task": task}
    schedules.append(event)
    save_schedules(schedules)
    return f"成功添加日程: [ID: {final_id}] {normalized_time} - {task}"

def add_schedule_with_date(date, clock_time, task):
    """通过 date + clock_time 组合时间后新增日程。"""
    date = str(date).strip()
    clock_time = str(clock_time).strip()
    task = str(task).strip()

    if not date or not clock_time or not task:
        return "错误：date、clock_time、task 不能为空。"

    combined_time = f"{date} {clock_time}"
    return add_schedule(time=combined_time, task=task)

def list_schedules():
    schedules = load_schedules()
    if not schedules:
        return "当前没有日程。"
    res = "当前日程列表:\n"
    for s in schedules:
        res += f"- [ID: {s['id']}] {s['time']}: {s['task']}\n"
    return res

def delete_schedule(event_id):
    schedules = load_schedules()
    new_schedules = [s for s in schedules if str(s.get("id")) != str(event_id)]
    if len(new_schedules) == len(schedules):
        return f"未找到 ID 为 {event_id} 的日程"
    save_schedules(new_schedules)
    return f"成功删除日程 ID {event_id}"

def update_schedule(event_id, new_time="", new_task=""):
    """按 ID 修改日程，new_time/new_task 至少提供一个。"""
    if not str(event_id).strip():
        return "错误：event_id 不能为空。"

    if not str(new_time).strip() and not str(new_task).strip():
        return "错误：请至少提供 new_time 或 new_task 之一。"

    schedules = load_schedules()
    target = None
    for item in schedules:
        if str(item.get("id")) == str(event_id):
            target = item
            break

    if not target:
        return f"未找到 ID 为 {event_id} 的日程"

    old_time = target.get("time", "")
    old_task = target.get("task", "")

    if str(new_time).strip():
        target["time"] = normalize_time_str(str(new_time))
    if str(new_task).strip():
        target["task"] = str(new_task).strip()

    save_schedules(schedules)
    return (
        f"成功修改日程 [ID: {event_id}] "
        f"{old_time} - {old_task} -> {target.get('time', '')} - {target.get('task', '')}"
    )

def reschedule_schedule(event_id, new_time):
    """仅修改时间。"""
    return update_schedule(event_id=event_id, new_time=new_time, new_task="")

def rename_schedule(event_id, new_task):
    """仅修改任务描述。"""
    return update_schedule(event_id=event_id, new_time="", new_task=new_task)

def parse_feishu_doc_ref(doc_url="", doc_token=""):
    """
    解析飞书文档引用，返回 (token, token_type)。
    token_type: docx / docs / wiki / unknown
    """
    explicit_token = str(doc_token).strip()
    if explicit_token:
        return explicit_token, "unknown"

    if not doc_url:
        return "", "unknown"

    parsed = urlparse(str(doc_url).strip())
    path = parsed.path or ""

    patterns = [
        ("docx", r"/docx/([A-Za-z0-9]+)"),
        ("docs", r"/docs/([A-Za-z0-9]+)"),
        ("wiki", r"/wiki/([A-Za-z0-9]+)"),
    ]
    for token_type, pattern in patterns:
        match = re.search(pattern, path)
        if match:
            return match.group(1), token_type

    return "", "unknown"

def get_feishu_tenant_access_token():
    app_id = os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        return "", "错误：未配置 FEISHU_APP_ID 或 FEISHU_APP_SECRET。"

    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": app_id, "app_secret": app_secret}

    try:
        response = requests.post(token_url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return "", f"错误：获取飞书 tenant_access_token 失败: {str(e)}"

    if data.get("code") != 0:
        return "", f"错误：获取飞书 token 失败: {data.get('msg', data)}"

    token = data.get("tenant_access_token", "")
    if not token:
        return "", "错误：飞书返回中缺少 tenant_access_token。"
    return token, ""

def resolve_wiki_node_to_document(wiki_token, headers):
    """
    将 wiki token 解析为真实文档 token。
    返回: (document_token, obj_type, error_message)
    """
    endpoint = "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node"
    try:
        response = requests.get(endpoint, headers=headers, params={"token": wiki_token}, timeout=20)
        data = response.json()
    except Exception as e:
        return "", "", f"错误：读取飞书 wiki 节点失败: {str(e)}"

    if response.status_code >= 400 and data.get("code") is None:
        return "", "", f"错误：读取飞书 wiki 节点失败: HTTP {response.status_code}"

    if data.get("code") != 0:
        return "", "", f"错误：飞书 wiki 接口返回失败: {data.get('msg', data)}"

    data_obj = data.get("data", {}) if isinstance(data.get("data", {}), dict) else {}
    node_obj = data_obj.get("node", {}) if isinstance(data_obj.get("node", {}), dict) else {}

    document_token = node_obj.get("obj_token") or data_obj.get("obj_token") or ""
    obj_type = node_obj.get("obj_type") or data_obj.get("obj_type") or ""

    if not document_token:
        return "", "", "错误：wiki 节点解析成功，但未拿到 obj_token。"

    return document_token, obj_type, ""

def fetch_feishu_raw_content(document_token, headers):
    """依次尝试多个正文接口，返回 (content, error_detail)。"""
    endpoints = [
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_token}/raw_content",
        f"https://open.feishu.cn/open-apis/docs/v1/documents/{document_token}/raw_content",
        f"https://open.feishu.cn/open-apis/doc/v2/{document_token}/raw_content",
    ]

    errors = []
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=headers, timeout=20)
            data = response.json()
        except Exception as e:
            errors.append(f"{endpoint}: {str(e)}")
            continue

        if response.status_code >= 400 and data.get("code") is None:
            errors.append(f"{endpoint}: HTTP {response.status_code}")
            continue

        if data.get("code") != 0:
            errors.append(f"{endpoint}: {data.get('msg', data)}")
            continue

        data_obj = data.get("data", {})
        if isinstance(data_obj, dict):
            content = data_obj.get("content", "") or data_obj.get("raw_content", "")
            if content:
                return content, ""

        errors.append(f"{endpoint}: 接口成功但内容为空")

    return "", "\n".join(errors)

def read_feishu_doc(doc_url="", doc_token=""):
    """
    读取飞书文档正文（raw content）。
    参数二选一：doc_url 或 doc_token。
    """
    token, token_type = parse_feishu_doc_ref(doc_url=doc_url, doc_token=doc_token)
    if not token:
        return "错误：无法识别飞书文档 token，请传入 doc_token 或合法的 doc_url。"

    tenant_token, err = get_feishu_tenant_access_token()
    if err:
        return err

    headers = {"Authorization": f"Bearer {tenant_token}"}
    document_token = token

    # wiki 链接需要先将 wiki_token 解析为文档 token
    if token_type == "wiki":
        document_token, obj_type, wiki_err = resolve_wiki_node_to_document(token, headers)
        if wiki_err:
            return (
                f"{wiki_err}\n"
                "请确认应用已开通权限 wiki:wiki:readonly，且应用可访问该知识库节点。"
            )
        if obj_type and obj_type not in {"docx", "docs", "doc"}:
            return f"错误：该 wiki 节点类型为 {obj_type}，当前仅支持 doc/docx/docs。"

    content, fetch_err = fetch_feishu_raw_content(document_token, headers)
    if not content:
        return (
            "错误：读取飞书文档正文失败。\n"
            f"{fetch_err}\n"
            "请确认应用已开通 docx:document:readonly、docs:document:readonly（旧文档）以及 wiki:wiki:readonly，"
            "并将应用添加为该文档/知识库可访问成员。"
        )

    return f"成功读取飞书文档 (token={document_token})，内容如下：\n\n{content}"

def read_document(file_path):
    """读取本地文档内容，优先搜索下载目录"""
    # 如果 Agent 传入了包含路径的字符串，提取文件名
    filename = os.path.basename(file_path.strip("'\" "))
    
    # 搜索优先级：1. Downloads 目录, 2. Task1/data/uploads 目录, 3. Task1/test 目录, 4. Task1/data 目录
    search_paths = [
        os.path.join(DOWNLOADS_DIR, filename),
        os.path.join(UPLOADS_DIR, filename),
        os.path.join(TEST_DIR, filename),
        os.path.join(DATA_DIR, filename)
    ]
    
    # 也支持 Agent 传入完整的绝对路径（如果它够聪明的话）
    if os.path.isabs(file_path.strip("'\" ")):
        search_paths.insert(0, file_path.strip("'\" "))

    target_path = None
    for p in search_paths:
        if os.path.exists(p):
            target_path = p
            break
    
    if not target_path:
        return f"错误：文件 {filename} 不存在于 下载目录 或 项目 test 目录中。"
    
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            return f"成功读取文件 ({target_path})，内容如下：\n\n{content}"
    except Exception as e:
        return f"读取文件失败: {str(e)}"
