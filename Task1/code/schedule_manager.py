import json
import os
from datetime import datetime

# 将数据文件存放在 ../data/ 目录下
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test"))
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

def read_document(file_path):
    """读取本地文档内容，优先搜索下载目录"""
    # 如果 Agent 传入了包含路径的字符串，提取文件名
    filename = os.path.basename(file_path.strip("'\" "))
    
    # 搜索优先级：1. Downloads 目录, 2. Task1/test 目录, 3. Task1/data 目录
    search_paths = [
        os.path.join(DOWNLOADS_DIR, filename),
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
