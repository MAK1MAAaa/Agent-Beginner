import json
import os

# 将数据文件存放在 ../test/ 目录下
DB_FILE = os.path.join(os.path.dirname(__file__), "..", "test", "schedules.json")

def load_schedules():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_schedules(schedules):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

def add_schedule(time, task):
    schedules = load_schedules()
    new_id = len(schedules) + 1
    event = {"id": new_id, "time": time, "task": task}
    schedules.append(event)
    save_schedules(schedules)
    return f"成功添加日程: [ID: {new_id}] {time} - {task}"

def list_schedules():
    schedules = load_schedules()
    if not schedules:
        return "当前没有日程。"
    res = "当前日程列表:\n"
    for s in schedules:
        res += f"- [ID: {s['id']}] {s['time']}: {s['task']}\n"
    return res

def update_schedule(event_id, time=None, task=None):
    schedules = load_schedules()
    found = False
    for s in schedules:
        if str(s["id"]) == str(event_id):
            if time: s["time"] = time
            if task: s["task"] = task
            found = True
            break
    if found:
        save_schedules(schedules)
        return f"成功更新日程 ID {event_id}"
    return f"未找到 ID 为 {event_id} 的日程"

def delete_schedule(event_id):
    schedules = load_schedules()
    new_schedules = [s for s in schedules if str(s["id"]) != str(event_id)]
    if len(new_schedules) == len(schedules):
        return f"未找到 ID 为 {event_id} 的日程"
    save_schedules(new_schedules)
    return f"成功删除日程 ID {event_id}"

def read_document(file_path):
    """读取本地文档内容（如 Markdown 笔记或聊天记录）"""
    # 为了安全和演示，我们限制只能读取 Task1/test 目录下的文件
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test"))
    target_path = os.path.abspath(os.path.join(base_dir, file_path))
    
    if not target_path.startswith(base_dir):
        return "错误：只能读取 test 目录下的文件。"
    
    if not os.path.exists(target_path):
        return f"错误：文件 {file_path} 不存在。"
    
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取文件失败: {str(e)}"
