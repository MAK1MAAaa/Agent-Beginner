import json
import os

# 将数据文件存放在 ../test/ 目录下
DB_FILE = os.path.join(os.path.dirname(__file__), "..", "test", "schedules.json")

def load_schedules():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

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
    for s in schedules:
        if s["id"] == int(event_id):
            if time: s["time"] = time
            if task: s["task"] = task
            save_schedules(schedules)
            return f"成功更新日程 ID {event_id}"
    return f"未找到 ID 为 {event_id} 的日程"

def delete_schedule(event_id):
    schedules = load_schedules()
    new_schedules = [s for s in schedules if s["id"] != int(event_id)]
    if len(new_schedules) == len(schedules):
        return f"未找到 ID 为 {event_id} 的日程"
    save_schedules(new_schedules)
    return f"成功删除日程 ID {event_id}"
