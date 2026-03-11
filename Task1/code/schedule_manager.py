import json
import os

# 将数据文件存放在 ../data/ 目录下
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test"))
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

def add_schedule(time, task):
    schedules = load_schedules()
    if schedules:
        new_id = max(s.get("id", 0) for s in schedules) + 1
    else:
        new_id = 1
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

def delete_schedule(event_id):
    schedules = load_schedules()
    new_schedules = [s for s in schedules if str(s.get("id")) != str(event_id)]
    if len(new_schedules) == len(schedules):
        return f"未找到 ID 为 {event_id} 的日程"
    save_schedules(new_schedules)
    return f"成功删除日程 ID {event_id}"

def read_document(file_path):
    """读取本地文档内容"""
    # 如果 Agent 传入的是包含引号或路径的字符串，进行清理
    clean_path = os.path.basename(file_path.strip("'\" "))
    
    target_path = os.path.join(TEST_DIR, clean_path)
    
    if not os.path.exists(target_path):
        # 尝试在 data 目录下也找一下（增加容错）
        alt_path = os.path.join(DATA_DIR, clean_path)
        if os.path.exists(alt_path):
            target_path = alt_path
        else:
            return f"错误：文件 {clean_path} 不存在于 test 或 data 目录中。请确保文件名正确且文件已上传。"
    
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            return f"成功读取文件 {clean_path}，内容如下：\n\n{content}"
    except Exception as e:
        return f"读取文件失败: {str(e)}"
