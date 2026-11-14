"""Persistent memory (SQLite) for StudyMate.

Three kinds of memory are kept:
  * semantic / task memory  - the `tasks` table (what the student has to do)
  * feedback memory         - the `feedback` table, each item stored with a numeric reward
  * episodic memory         - the `agent_runs` table: every planning run, which tasks were
                              planned and which were left out (used to avoid starving a task)
Short-term memory (the last few turns) lives inside the agent object.
"""
import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("STUDYMATE_DB", Path(__file__).parent / "data" / "studymate.db"))

REWARD = {"Helpful": 1.0, "Too little work": -0.25, "Too much work": -0.5, "Too difficult": -0.5}

_COLUMNS = {   # columns added after the first version -> migrated automatically
    "tasks": {"created_at": "TEXT DEFAULT ''"},
    "feedback": {"reward": "REAL DEFAULT 0", "run_id": "INTEGER"},
    "agent_runs": {"intent": "TEXT", "plan_json": "TEXT", "excluded_ids": "TEXT",
                   "latency_ms": "REAL", "llm_status": "TEXT"},
}


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create tables and upgrade older databases (e.g. one created by an earlier version)."""
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            subject TEXT DEFAULT '',
            deadline TEXT NOT NULL,
            priority TEXT NOT NULL CHECK(priority IN ('High','Medium','Low')),
            study_hours REAL NOT NULL CHECK(study_hours > 0),
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Completed')),
            created_at TEXT NOT NULL DEFAULT ''
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_type TEXT NOT NULL,
            feedback_text TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            reward REAL DEFAULT 0,
            run_id INTEGER
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS agent_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_request TEXT,
            available_hours REAL,
            selected_tool TEXT,
            result_summary TEXT,
            created_at TEXT NOT NULL DEFAULT '',
            intent TEXT, plan_json TEXT, excluded_ids TEXT, latency_ms REAL, llm_status TEXT
        )""")
        for table, cols in _COLUMNS.items():          # migration for old databases
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


# ------------------------------------------------------------------ tasks
def get_tasks():
    with connect() as conn:
        rows = conn.execute("SELECT id,task_name,COALESCE(subject,''),deadline,priority,study_hours,status "
                            "FROM tasks ORDER BY deadline, id").fetchall()
    keys = ["id", "task_name", "subject", "deadline", "priority", "study_hours", "status"]
    return [dict(zip(keys, r)) for r in rows]


def add_task(name, subject, deadline, priority, hours):
    with connect() as conn:
        conn.execute("INSERT INTO tasks(task_name,subject,deadline,priority,study_hours,status,created_at) "
                     "VALUES(?,?,?,?,?,'Pending',?)",
                     (name, subject, deadline, priority, hours, date.today().isoformat()))


def update_task(task_id, hours=None, deadline=None, priority=None):
    with connect() as conn:
        if hours is not None:
            conn.execute("UPDATE tasks SET study_hours=? WHERE id=?", (float(hours), int(task_id)))
        if deadline is not None:
            conn.execute("UPDATE tasks SET deadline=? WHERE id=?", (deadline, int(task_id)))
        if priority is not None:
            conn.execute("UPDATE tasks SET priority=? WHERE id=?", (priority, int(task_id)))


def set_task_status(task_id, status):
    with connect() as conn:
        conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, int(task_id)))


def delete_task(task_id):
    with connect() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (int(task_id),))


def seed_demo_tasks():
    """Insert a small demo data set (only if the task table is empty). Returns rows added."""
    if get_tasks():
        return 0
    from datetime import timedelta
    d = lambda n: (date.today() + timedelta(days=n)).isoformat()
    demo = [("DAT404 project report", "Intelligent Agents", d(2), "High", 4.0),
            ("Statistics problem set", "Statistics", d(1), "High", 2.0),
            ("Read Chapter 5", "Databases", d(6), "Medium", 1.5),
            ("Prepare quiz revision", "Statistics", d(4), "Medium", 2.5),
            ("Lab write-up", "Databases", d(9), "Low", 3.0),
            ("Reading journal", "Ethics", d(12), "Low", 1.0)]
    for row in demo:
        add_task(*row)
    return len(demo)


# --------------------------------------------------------------- feedback
def save_feedback(feedback_type, feedback_text, run_id=None):
    reward = REWARD.get(feedback_type, 0.0)
    with connect() as conn:
        conn.execute("INSERT INTO feedback(feedback_type,feedback_text,created_at,reward,run_id) VALUES(?,?,?,?,?)",
                     (feedback_type, feedback_text, datetime.now().isoformat(timespec="seconds"), reward, run_id))


def latest_feedback():
    rows = feedback_history(1)
    return rows[0] if rows else None


def feedback_history(n=10):
    """Most recent feedback first."""
    with connect() as conn:
        rows = conn.execute("SELECT feedback_type,COALESCE(feedback_text,''),created_at,COALESCE(reward,0) "
                            "FROM feedback ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [{"feedback_type": r[0], "feedback_text": r[1], "created_at": r[2], "reward": r[3]} for r in rows]


# ----------------------------------------------------- episodic memory
def log_agent_run(request, hours, tools, summary, intent=None, plan=None,
                  excluded_ids=None, latency_ms=None, llm_status=None):
    plan_json = json.dumps([{k: v for k, v in p.items()} for p in (plan or [])], default=str)
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO agent_runs(user_request,available_hours,selected_tool,result_summary,created_at,"
            "intent,plan_json,excluded_ids,latency_ms,llm_status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (request, hours, tools, summary, datetime.now().isoformat(timespec="seconds"),
             intent, plan_json, json.dumps(excluded_ids or []), latency_ms, llm_status))
        return cur.lastrowid


def recent_runs(n=5):
    """Most recent runs first, with excluded task ids decoded."""
    with connect() as conn:
        rows = conn.execute("SELECT id,user_request,available_hours,selected_tool,intent,excluded_ids,"
                            "latency_ms,llm_status,created_at FROM agent_runs ORDER BY id DESC LIMIT ?",
                            (n,)).fetchall()
    out = []
    for r in rows:
        try:
            excluded = json.loads(r[5] or "[]")
        except ValueError:
            excluded = []
        out.append({"id": r[0], "request": r[1], "hours": r[2], "tools": r[3] or "", "intent": r[4],
                    "excluded_ids": excluded, "latency_ms": r[6], "llm_status": r[7], "created_at": r[8]})
    return out


def tool_usage_counts():
    counts = {}
    for run in recent_runs(1000):
        for t in filter(None, run["tools"].split(",")):
            counts[t] = counts.get(t, 0) + 1
    return counts
