"""Tools available to the StudyMate agent (DAT404 Milestone 2 / Week 10).

Every tool is a plain, deterministic Python function so that its output can be
tested and traced. The LLM never calls these directly: the agent's tool-selection
POLICY (select_tools) decides which tools run, and run_tool() wraps each call so a
failing tool cannot crash the agent.
"""
import re
import time
from datetime import date

PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}


def _days_left(task, today):
    return (date.fromisoformat(task["deadline"]) - today).days


# ----------------------------------------------------------------- Tool 1
def task_priority_tool(task, today=None, boost=0.0):
    """Score a task from priority weight + deadline urgency (+ memory-based boost)."""
    today = today or date.today()
    days_left = max(_days_left(task, today), 0)
    urgency = 1 / (days_left + 1)
    return PRIORITY_WEIGHT.get(task["priority"], 1) + 5 * urgency + boost


# ----------------------------------------------------------------- Tool 2
def study_time_tool(tasks):
    """Sum the estimated study hours of the given tasks."""
    return sum(float(t["study_hours"]) for t in tasks)


# ----------------------------------------------------------------- Tool 3
def deadline_risk_tool(tasks, today=None, daily_capacity=3.0):
    """Check whether pending work can realistically be finished before each deadline.

    Tasks are taken in deadline order; the cumulative hours due by each deadline are
    compared with daily_capacity * (days available). Returns one dict per task.
    """
    today = today or date.today()
    pending = sorted((t for t in tasks if t["status"] == "Pending"),
                     key=lambda t: (t["deadline"], t["task_name"]))
    cumulative, report = 0.0, []
    for t in pending:
        days = _days_left(t, today)
        cumulative += float(t["study_hours"])
        capacity = daily_capacity * max(days + 1, 0)
        if days < 0:
            status, msg = "Overdue", f"Overdue by {-days} day(s)."
        elif cumulative > capacity:
            status = "At risk"
            msg = (f"{cumulative:g}h of work is due by this date but only about "
                   f"{capacity:g}h of study capacity exists ({daily_capacity:g}h/day).")
        else:
            status, msg = "On track", "Enough time available at the assumed daily capacity."
        report.append({"id": t.get("id"), "Task": t["task_name"], "Deadline": t["deadline"],
                       "Days left": days, "Status": status, "Note": msg})
    return report


# ----------------------------------------------------------------- Tool 4
_STOP = {"the", "a", "an", "my", "and", "for", "on", "of", "to", "in", "with", "me", "i",
         "help", "study", "plan", "task", "tasks", "work", "hours", "hour", "have", "need",
         "focus", "today", "urgent", "priority", "high", "low", "medium", "please", "some"}


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def subject_match_tool(request_or_focus, tasks):
    """Ground a free-text focus in REAL records: return ids of pending tasks whose
    subject or name shares a meaningful word with the text. Cannot invent tasks."""
    wanted = _tokens(request_or_focus)
    matched = []
    for t in tasks:
        if t["status"] != "Pending":
            continue
        if wanted & (_tokens(t.get("subject")) | _tokens(t["task_name"])):
            matched.append(t["id"])
    return matched


TOOL_REGISTRY = {
    "task_priority_tool": "Scores tasks from priority and deadline urgency",
    "study_time_tool": "Totals the estimated hours of pending work",
    "deadline_risk_tool": "Flags overdue or unrealistic deadlines",
    "subject_match_tool": "Matches a requested subject to stored tasks",
}


# ----------------------------------------------------------- tool selection
RISK_WORDS = ["risk", "behind", "overdue", "realistic", "enough time", "can i finish",
              "can i make", "workload", "overload", "manageable"]


def select_tools(request, intent="create_study_plan", subject_hit=False):
    """Transparent tool-selection policy. The LLM may suggest an intent, but the tools
    are chosen here by explicit rules, then validated against TOOL_REGISTRY.

    Returns a list of {"tool": name, "reason": why}.
    """
    text = (request or "").lower()
    chosen = {}

    def add(name, reason):
        if name in TOOL_REGISTRY and name not in chosen:
            chosen[name] = reason

    if intent in ("create_study_plan", "urgent_only", "focus_subject"):
        add("task_priority_tool", "A plan needs tasks ranked by priority and urgency.")
    if intent in ("create_study_plan", "focus_subject", "workload_review"):
        add("study_time_tool", "Compare pending workload with the available time.")
    if intent in ("urgent_only", "workload_review") or any(w in text for w in RISK_WORDS):
        add("deadline_risk_tool", "Urgency or feasibility was asked about, so deadlines are checked.")
    if intent == "focus_subject" or subject_hit:
        add("subject_match_tool", "A subject/task was mentioned; match it to stored records.")
    if not chosen:
        add("task_priority_tool", "Default tool.")
        add("study_time_tool", "Default tool.")
    return [{"tool": k, "reason": v} for k, v in chosen.items()]


def run_tool(name, fn, *args, fail_tools=(), **kwargs):
    """Execute a tool safely. Returns dict(ok, result, error, ms).

    `fail_tools` lets the evaluation inject failures to test error handling."""
    start = time.perf_counter()
    try:
        if name in fail_tools:
            raise RuntimeError(f"Injected failure in {name}")
        result = fn(*args, **kwargs)
        return {"tool": name, "ok": True, "result": result, "error": None,
                "ms": round((time.perf_counter() - start) * 1000, 3)}
    except Exception as exc:  # noqa: BLE001 - tool failure must never crash the agent
        return {"tool": name, "ok": False, "result": None, "error": str(exc),
                "ms": round((time.perf_counter() - start) * 1000, 3)}
