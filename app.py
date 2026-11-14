"""StudyMate AI - Streamlit front end."""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from agent import StudyMateAgent
from guardrails import clean_task_text
from memory import (add_task, delete_task, feedback_history, init_db, get_tasks, recent_runs,
                    save_feedback, seed_demo_tasks, set_task_status, tool_usage_counts, update_task)

st.set_page_config(page_title="StudyMate AI", page_icon="📚", layout="wide")

st.markdown("""
<style>
:root{--brown:#6B4F3A;--brown2:#8A6A4F;--cream:#FAF8F4;--sand:#F0E8DC;--line:#E1D4C3;--ink:#3E342B}
.stApp{background:var(--cream);color:var(--ink)}
[data-testid="stSidebar"]{background:#EDE5D8}
h1,h2,h3{color:#4B382A;letter-spacing:-.01em}
div.stButton>button{background:var(--brown);color:#fff;border:0;border-radius:10px;padding:.5rem 1rem;font-weight:600}
div.stButton>button:hover{background:var(--brown2);color:#fff}
div[data-testid="stMetric"]{background:var(--sand);border:1px solid var(--line);padding:14px 16px;border-radius:12px}
.hero{background:linear-gradient(135deg,#6B4F3A,#A07D5C);color:#fff;padding:22px 26px;border-radius:16px;margin-bottom:14px}
.hero h1{color:#fff;margin:0;font-size:1.9rem}.hero p{margin:.3rem 0 0;opacity:.9}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:600;margin-right:6px}
.b-high{background:#F6D5CF;color:#8C2A1B}.b-medium{background:#F8E7C2;color:#7A5A0B}.b-low{background:#DCEBD5;color:#2F5D23}
.b-over{background:#8C2A1B;color:#fff}.b-soon{background:#E7B76B;color:#4B2E00}.b-ok{background:#E1D4C3;color:#4B382A}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-bottom:10px}
.plan{background:#fff;border-left:6px solid var(--brown);border:1px solid var(--line);border-left-width:6px;
      border-radius:12px;padding:12px 16px;margin-bottom:10px}
.plan .hrs{float:right;font-weight:700;color:var(--brown);font-size:1.15rem}
.muted{color:#8A7B6C;font-size:.85rem}
</style>""", unsafe_allow_html=True)

init_db()
if "agent" not in st.session_state:
    st.session_state["agent"] = StudyMateAgent()     # keeps short-term memory between turns
agent = st.session_state["agent"]

PRI_CLASS = {"High": "b-high", "Medium": "b-medium", "Low": "b-low"}


def due_badge(deadline):
    days = (date.fromisoformat(deadline) - date.today()).days
    if days < 0:
        return f'<span class="badge b-over">Overdue {-days}d</span>'
    if days <= 2:
        return f'<span class="badge b-soon">Due in {days}d</span>' if days else '<span class="badge b-soon">Due today</span>'
    return f'<span class="badge b-ok">Due in {days}d</span>'


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("📚 StudyMate")
    st.caption("Your academic planning agent")
    page = st.radio("Navigation", ["Dashboard", "My Tasks", "Study Planner", "Feedback",
                                   "Evaluation", "About the Agent"], label_visibility="collapsed")
    st.divider()
    if not get_tasks():
        if st.button("Load demo tasks"):
            seed_demo_tasks()
            st.rerun()
    st.caption("Plan better. Study smarter.")

tasks = get_tasks()
pending_tasks = [t for t in tasks if t["status"] == "Pending"]
total, completed = len(tasks), sum(t["status"] == "Completed" for t in tasks)
pending_hours = sum(float(t["study_hours"]) for t in pending_tasks)

st.markdown('<div class="hero"><h1>StudyMate AI</h1><p>An agent that understands your request, picks tools, '
            'remembers your progress and adapts to your feedback.</p></div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("All tasks", total)
c2.metric("Completed", completed)
c3.metric("Pending", total - completed)
c4.metric("Pending hours", f"{pending_hours:g}")
if total:
    st.progress(completed / total, text=f"{completed / total:.0%} of tasks completed")
st.write("")

# ---------------------------------------------------------------- Dashboard
if page == "Dashboard":
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Upcoming deadlines")
        if pending_tasks:
            for t in sorted(pending_tasks, key=lambda x: x["deadline"])[:6]:
                st.markdown(
                    f'<div class="card"><b>{t["task_name"]}</b><br>'
                    f'<span class="badge {PRI_CLASS[t["priority"]]}">{t["priority"]}</span>{due_badge(t["deadline"])}'
                    f'<span class="muted">{t["subject"] or "No subject"} · {t["study_hours"]:g} h · {t["deadline"]}</span></div>',
                    unsafe_allow_html=True)
        else:
            st.info("No pending tasks. Add one in **My Tasks** or load the demo tasks from the sidebar.")
    with right:
        st.subheader("Workload by subject")
        if pending_tasks:
            df = pd.DataFrame(pending_tasks)
            df["subject"] = df["subject"].replace("", "No subject")
            st.bar_chart(df.groupby("subject")["study_hours"].sum(), color="#6B4F3A")
        else:
            st.caption("Chart appears once you have pending tasks.")

# ----------------------------------------------------------------- My Tasks
elif page == "My Tasks":
    st.subheader("Manage study tasks")
    with st.expander("➕ Add a new task", expanded=not tasks):
        with st.form("new_task", clear_on_submit=True):
            a, b = st.columns(2)
            task_name = a.text_input("Task name", placeholder="e.g. DAT404 project report")
            subject = b.text_input("Subject", placeholder="e.g. Intelligent Agents")
            d1, d2, d3 = st.columns(3)
            deadline = d1.date_input("Deadline", value=date.today() + timedelta(days=7))
            priority = d2.selectbox("Priority", ["High", "Medium", "Low"])
            hours = d3.number_input("Estimated study hours", 0.5, 100.0, 2.0, 0.5)
            submitted = st.form_submit_button("Add task")
        if submitted:
            name = clean_task_text(task_name)
            if name:
                add_task(name, clean_task_text(subject, 60), deadline.isoformat(), priority, float(hours))
                st.success("Task saved.")
                st.rerun()
            else:
                st.warning("Enter a task name.")

    f1, f2 = st.columns([2, 2])
    show = f1.radio("Show", ["Pending", "Completed", "All"], horizontal=True)
    sort_by = f2.selectbox("Sort by", ["Deadline", "Priority"])
    rows = [t for t in tasks if show == "All" or t["status"] == show]
    rows.sort(key=(lambda x: x["deadline"]) if sort_by == "Deadline"
              else (lambda x: ({"High": 0, "Medium": 1, "Low": 2}[x["priority"]], x["deadline"])))
    if not rows:
        st.info("Nothing to show here yet.")
    for task in rows:
        with st.container(border=True):
            a, b, c = st.columns([5, 2, 1])
            a.markdown(f"**{task['task_name']}**")
            a.markdown(f'<span class="badge {PRI_CLASS[task["priority"]]}">{task["priority"]}</span>'
                       f'{due_badge(task["deadline"])}<span class="muted">{task["subject"] or "No subject"} · '
                       f'{task["study_hours"]:g} h · {task["deadline"]}</span>', unsafe_allow_html=True)
            done = b.checkbox("Completed", value=task["status"] == "Completed", key=f"done_{task['id']}")
            if done != (task["status"] == "Completed"):
                set_task_status(task["id"], "Completed" if done else "Pending")
                st.rerun()
            if c.button("Delete", key=f"del_{task['id']}"):
                delete_task(task["id"])
                st.rerun()
            with st.expander("Edit"):
                e1, e2 = st.columns(2)
                nh = e1.number_input("Hours", 0.5, 100.0, float(task["study_hours"]), 0.5, key=f"h_{task['id']}")
                nd = e2.date_input("Deadline", date.fromisoformat(task["deadline"]), key=f"d_{task['id']}")
                if st.button("Save changes", key=f"s_{task['id']}"):
                    update_task(task["id"], hours=nh, deadline=nd.isoformat())
                    st.rerun()

# ------------------------------------------------------------ Study Planner
elif page == "Study Planner":
    st.subheader("Build a study plan")
    st.write("Describe what you need. The agent interprets the request, chooses tools, checks your deadlines, "
             "applies what it learned from your feedback and double-checks its own plan.")
    examples = ["I have 2 hours today. Focus on my most urgent tasks.",
                "I want to study statistics for 90 minutes",
                "Can I finish everything before my deadlines?"]
    cols = st.columns(len(examples))
    for col, ex in zip(cols, examples):
        if col.button(ex, key=ex):
            st.session_state["req_text"] = ex
    request = st.text_area("Your request", key="req_text", max_chars=500,
                           placeholder="e.g. I have 2 hours today. Help me focus on urgent, high-priority tasks.")
    available = st.number_input("Available study hours (default)", 0.5, 16.0, 2.0, 0.5,
                                help="Used when your request does not mention a time. A time in the request wins.")
    if st.button("Ask StudyMate to plan", type="primary"):
        with st.spinner("StudyMate is thinking..."):
            st.session_state["last_plan"] = agent.plan(request or "", available)
            st.session_state["last_llm_status"] = st.session_state["last_plan"]["llm_status"]

    result = st.session_state.get("last_plan")
    if result:
        if result["blocked"]:
            st.error(result["explanation"])
        else:
            for w in result["warnings"]:
                st.warning(w)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Intent", result["intent"].replace("_", " "))
            m2.metric("Time budget", f"{result['planning_budget']:g} h", f"{result['budget_factor']:.0%} of entered")
            m3.metric("LLM status", result["llm_status"].replace("_", " "))
            m4.metric("Response time", f"{result['latency_ms']:.0f} ms")

            if result.get("llm_note"):
                st.markdown(f'<div class="card">🤖 <b>Coach note</b> <span class="muted">(written by the local LLM, '
                            f'checked against your plan)</span><br>{result["llm_note"]}</div>', unsafe_allow_html=True)
            elif result["llm_status"] != "ok":
                st.caption("🔌 LLM not used for this request (" + result["llm_status"].replace("_", " ") +
                           "). The rule-based interpreter handled it.")

            if result["mode"] == "workload_review":
                st.subheader("Deadline feasibility")
            else:
                st.subheader("Your recommended study plan")
                if not result["plan"]:
                    st.info("No pending tasks to plan. Add a task in My Tasks.")
                for i, p in enumerate(result["plan"], 1):
                    st.markdown(
                        f'<div class="plan"><span class="hrs">{p["Planned Hours"]:g} h</span>'
                        f'<b>{i}. {p["Task"]}</b><br>'
                        f'<span class="badge {PRI_CLASS[p["Priority"]]}">{p["Priority"]}</span>'
                        f'<span class="muted">{p["Subject"] or "No subject"} · due {p["Deadline"]}</span><br>'
                        f'<span class="muted">Sessions: {p["Sessions"]}</span><br>'
                        f'<span class="muted">Why: {p["Why"]}</span></div>', unsafe_allow_html=True)
                if result["plan"]:
                    st.metric("Total planned study time", f"{sum(p['Planned Hours'] for p in result['plan']):g} hours")

            if result["risks"]:
                st.markdown("**Deadline check**")
                st.dataframe(pd.DataFrame(result["risks"]).drop(columns=["id"]), use_container_width=True, hide_index=True)

            st.markdown("**Why this plan was recommended**")
            st.write(result["explanation"])

            with st.expander("🔎 Agent trace (observability)"):
                for s in result["trace"]:
                    detail = {k: v for k, v in s.items() if k not in ("step", "ms")}
                    st.markdown(f"**{s['step']}**" + (f" — {s['ms']} ms" if "ms" in s else ""))
                    st.json(detail, expanded=False)
            with st.expander("✅ Self-check (reflection)"):
                for c in result["reflection"]:
                    st.write(("✅ " if c["passed"] else "❌ ") + c["check"])
        st.caption("Review the recommendation before following it. StudyMate never submits work or makes academic decisions for you.")

# ----------------------------------------------------------------- Feedback
elif page == "Feedback":
    st.subheader("Feedback and adaptation")
    st.write("Tell StudyMate how its last plan worked. Each answer becomes a reward score and adjusts the next plan's time budget.")
    fb = st.selectbox("How did the plan feel?", ["Helpful", "Too much work", "Too difficult", "Too little work"])
    note = st.text_area("Optional note", placeholder="For example, I had less time than expected.", max_chars=300)
    if st.button("Save feedback"):
        runs = recent_runs(1)
        save_feedback(fb, note.strip(), runs[0]["id"] if runs else None)
        st.success("Feedback saved. The next plan will adapt.")
    hist = feedback_history(20)
    if hist:
        st.markdown("**Reward over time** (Helpful +1, Too little −0.25, Too much / Too difficult −0.5)")
        df = pd.DataFrame(hist[::-1])
        df["interaction"] = range(1, len(df) + 1)
        st.line_chart(df.set_index("interaction")["reward"], color="#6B4F3A")
        st.dataframe(pd.DataFrame(hist)[["created_at", "feedback_type", "feedback_text", "reward"]],
                     use_container_width=True, hide_index=True)

# --------------------------------------------------------------- Evaluation
elif page == "Evaluation":
    st.subheader("Evaluation")
    st.write("Runs the scenario-based test suite (planner, time parsing, interpretation, tool selection, safety, "
             "robustness, performance). The LLM is switched off so the results are repeatable.")
    if st.button("Run evaluation"):
        from evaluation import run_evaluation
        res, summ = run_evaluation()
        st.session_state["eval_results"], st.session_state["eval_summary"] = res, summ
    if "eval_summary" in st.session_state:
        s = st.session_state["eval_summary"]
        a, b, c, d, e = st.columns(5)
        a.metric("Test cases", s["total"])
        b.metric("Passed", s["passed"])
        c.metric("Success rate", f"{s['success_rate']:.1%}")
        d.metric("Tool-selection acc.", f"{s['tool_selection_accuracy']:.0%}")
        e.metric("Mean latency", f"{s['latency_ms']['mean']:.2f} ms")
        st.markdown("**Success rate by test group**")
        st.bar_chart(pd.DataFrame({k: v["rate"] * 100 for k, v in s["by_group"].items()}, index=["% passed"]).T, color="#6B4F3A")
        st.markdown("**Intent confusion matrix** (rows = expected, columns = predicted)")
        st.dataframe(pd.DataFrame(s["confusion_matrix"]).T, use_container_width=True)
        st.dataframe(pd.DataFrame(st.session_state["eval_results"]), use_container_width=True, hide_index=True)
        st.markdown("**Known limitations (not counted in the score)**")
        st.dataframe(pd.DataFrame(s["limitations"]), use_container_width=True, hide_index=True)
    usage = tool_usage_counts()
    if usage:
        st.markdown("**Live tool-usage frequency** (from logged agent runs)")
        st.bar_chart(pd.Series(usage), color="#8A6A4F")

# ---------------------------------------------------------- About the Agent
elif page == "About the Agent":
    st.subheader("About the agent")
    st.markdown("""
**Problem.** Students juggle several deadlines and struggle to decide what to study in a limited amount of time.

**PEAS**
| | |
|---|---|
| **Performance** | Plan respects time budget, urgent work first, no invented tasks, student rates plan as helpful |
| **Environment** | Student's task list, deadlines, available hours, feedback history (partially observable, dynamic, sequential) |
| **Actuators** | Returns a ranked, time-boxed study plan with explanations and risk warnings |
| **Sensors** | Free-text request, task database, feedback, past runs |

**Agent loop.** perceive & guard → extract time → interpret (LLM or rules) → choose tools → recall memory →
run tools → plan & adapt → self-check → return plan → feedback.
""")
    fig = Path(__file__).parent / "docs" / "figures" / "architecture.png"
    if fig.exists():
        st.image(str(fig), caption="StudyMate architecture")
    runs = recent_runs(10)
    if runs:
        st.markdown("**Recent agent runs (episodic memory)**")
        st.dataframe(pd.DataFrame(runs)[["created_at", "request", "intent", "tools", "llm_status", "latency_ms"]],
                     use_container_width=True, hide_index=True)
