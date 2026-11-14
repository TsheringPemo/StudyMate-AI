"""Planning component: ranks tasks, applies feedback-based adaptation and allocates hours."""
from datetime import date

from tools import task_priority_tool

# Reward-style adjustment learned from the student's feedback (Week 5-6 concept).
FEEDBACK_ADJUSTMENT = {"Too much work": -0.25, "Too difficult": -0.25,
                       "Helpful": 0.0, "Too little work": 0.25}
HISTORY_WEIGHTS = [0.5, 0.3, 0.2]       # newest feedback counts most
MIN_FACTOR, MAX_FACTOR = 0.5, 1.0       # never plan more than the student said they have
MAX_SESSION_HOURS = 1.5
MIN_BLOCK = 0.25


def budget_factor(feedback_history):
    """Weighted average of the last 3 feedback items (newest first) -> budget multiplier.

    One 'Too much work'  -> 0.75   (matches the original 25 % rule)
    'Too little work'    -> undoes earlier cuts but never exceeds the entered time.
    """
    history = [f for f in (feedback_history or []) if f in FEEDBACK_ADJUSTMENT][:3]
    if not history:
        return 1.0
    weights = HISTORY_WEIGHTS[:len(history)]
    adj = sum(w * FEEDBACK_ADJUSTMENT[f] for w, f in zip(weights, history)) / sum(weights)
    return round(max(MIN_FACTOR, min(MAX_FACTOR, 1.0 + adj)), 4)


def split_sessions(hours):
    """Split planned hours into study blocks of at most MAX_SESSION_HOURS."""
    blocks, left = [], round(hours, 2)
    while left > 0:
        b = min(MAX_SESSION_HOURS, left)
        blocks.append(round(b, 2))
        left = round(left - b, 2)
    return " + ".join(f"{b:g}h" for b in blocks) + (" (10-min break between blocks)" if len(blocks) > 1 else "")


def _why(task, today, boost):
    days = (date.fromisoformat(task["deadline"]) - today).days
    when = f"overdue by {-days}d" if days < 0 else ("due today" if days == 0 else f"due in {days}d")
    note = f"{task['priority']} priority, {when}"
    if boost > 0:
        note += ", boosted because it was left out of recent plans"
    return note


def make_plan(tasks, available_hours, feedback_history=None, today=None,
              boosts=None, candidate_ids=None, score_fn=None):
    """Rank pending tasks and fit them into the (feedback-adjusted) time budget.

    feedback_history : list of feedback types, newest first (a single string also works)
    boosts           : {task_id: extra score} from episodic memory / subject focus
    candidate_ids    : optional set of task ids to restrict the plan to
    score_fn         : scoring function; the agent swaps in a fallback if the tool fails
    """
    today = today or date.today()
    boosts = boosts or {}
    if isinstance(feedback_history, str):
        feedback_history = [feedback_history]
    score_fn = score_fn or task_priority_tool

    pending = [t for t in tasks if t["status"] == "Pending"]
    if candidate_ids is not None:
        pending = [t for t in pending if t.get("id") in candidate_ids]

    def score(t):
        return score_fn(t, today, boosts.get(t.get("id"), 0.0))

    pending.sort(key=lambda t: (-score(t), t["deadline"], t["task_name"]))

    factor = budget_factor(feedback_history)
    budget = round(float(available_hours) * factor, 4)

    if factor < 1.0:
        note = (f"Recent feedback indicated overload, so the usable time budget was scaled "
                f"to {factor:.0%} of the time you entered.")
    elif feedback_history and feedback_history[0] == "Too little work":
        note = "Feedback said the last plan was too light; the full entered time is being used."
    else:
        note = "No workload reduction was needed from feedback."

    plan, remaining = [], budget
    for t in pending:
        if remaining < MIN_BLOCK:
            break
        amount = round(min(float(t["study_hours"]), remaining), 2)
        boost = boosts.get(t.get("id"), 0.0)
        why = _why(t, today, boost)
        if amount < float(t["study_hours"]):
            why += f"; partial ({amount:g} of {float(t['study_hours']):g}h)"
        plan.append({"Task": t["task_name"], "Subject": t["subject"], "Deadline": t["deadline"],
                     "Priority": t["priority"], "Planned Hours": amount,
                     "Sessions": split_sessions(amount), "Why": why, "_id": t.get("id")})
        remaining = round(remaining - amount, 4)

    planned_ids = {p["_id"] for p in plan}
    all_pending = [t for t in tasks if t["status"] == "Pending"]
    return {
        "plan": plan,
        "total_pending_hours": sum(float(t["study_hours"]) for t in all_pending),
        "budget": budget,
        "factor": factor,
        "adaptation": note,
        "excluded_ids": [t["id"] for t in all_pending if t.get("id") not in planned_ids],
    }
