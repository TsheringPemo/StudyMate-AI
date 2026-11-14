"""StudyMate agent: perceive -> guard -> interpret -> select tools -> recall memory ->
execute tools -> plan -> reflect -> act, with a full trace for observability.

Architecture choice (defended in the report): a SINGLE tool-using agent with a
deterministic core and an OPTIONAL LLM interpreter. The LLM only classifies the
request (intent + focus); numbers, ranking and hours always come from Python tools,
so the plan cannot be hallucinated.
"""
import json
import os
import re
import time
from collections import deque
from datetime import date

import requests

import memory
from guardrails import check_request, clamp_hours
from scheduler import make_plan
from tools import (TOOL_REGISTRY, deadline_risk_tool, run_tool, select_tools, study_time_tool,
                   subject_match_tool, task_priority_tool)

OLLAMA_URL = os.environ.get("STUDYMATE_OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.environ.get("STUDYMATE_MODEL", "qwen3:8b")   # e.g. set to qwen3:4b on a slower laptop
INTENTS = ["create_study_plan", "urgent_only", "focus_subject", "workload_review"]
DEFAULT_FOCUS = "highest priority and nearest deadline"

_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
              "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


# ------------------------------------------------------------ time extraction
def extract_hours(request, default_hours):
    """Find an explicitly mentioned study duration. Returns (hours, source).

    Handles '2 hours', '1.5 hrs', '3h', '90 minutes', 'two hours', 'an hour', 'half an hour'.
    Falls back to the form value when nothing is mentioned."""
    text = (request or "").lower()
    if not text:
        return float(default_hours), "form"
    if re.search(r"half an? hour|30 ?min", text) and not re.search(r"\d+\s*(hours?|hrs?)", text):
        return 0.5, "request"
    word_pat = "|".join(_NUM_WORDS)
    m = re.search(rf"\b({word_pat})\s*(hours?|hrs?)\b", text)
    if m:
        return float(_NUM_WORDS[m.group(1)]), "request"
    if re.search(r"\b(an|one)\s+hour\b", text):
        return 1.0, "request"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h)\b", text)
    if m:
        return float(m.group(1)), "request"
    m = re.search(r"(\d+)\s*(minutes?|mins?|m)\b", text)
    if m:
        return int(m.group(1)) / 60, "request"
    return float(default_hours), "form"


# ----------------------------------------------------- request interpretation
def rule_based_interpretation(request, tasks):
    """Deterministic fallback interpreter (also used when the LLM is off or fails)."""
    text = (request or "").lower()
    if not text.strip():
        return {"intent": "create_study_plan", "focus": DEFAULT_FOCUS}
    if any(w in text for w in ["can i finish", "am i behind", "workload", "how much", "realistic",
                               "enough time", "overloaded", "risk", "manageable"]):
        return {"intent": "workload_review", "focus": "deadline feasibility"}
    if subject_match_tool(text, tasks):
        return {"intent": "focus_subject", "focus": request.strip()[:80]}
    if any(w in text for w in ["urgent", "asap", "due soon", "most urgent", "tomorrow", "closest deadline"]):
        return {"intent": "urgent_only", "focus": "nearest deadlines"}
    return {"intent": "create_study_plan", "focus": DEFAULT_FOCUS}


def _parse_llm_json(content):
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip()
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
    return json.loads(content)


def check_llm(url=OLLAMA_URL, model=MODEL):
    """Ping Ollama. Returns dict(running, model_installed, models, message) for the UI."""
    base = url.rsplit("/api/", 1)[0]
    try:
        r = requests.get(base + "/api/tags", timeout=(2, 5))
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except (requests.RequestException, ValueError):
        return {"running": False, "model_installed": False, "models": [],
                "message": "Ollama is not running. Start it, or see docs/OLLAMA_SETUP.md."}
    installed = model in names
    msg = (f"Connected. Model '{model}' is ready." if installed else
           f"Ollama is running but '{model}' is not installed. Run: ollama pull {model}")
    return {"running": True, "model_installed": installed, "models": names, "message": msg}


def _numbers(text):
    return {round(float(x), 4) for x in re.findall(r"\d+(?:\.\d+)?", text or "")}


class StudyMateAgent:
    def __init__(self, use_llm=True, url=OLLAMA_URL, model=MODEL):
        self.use_llm, self.url, self.model = use_llm, url, model
        self.short_term = deque(maxlen=3)       # short-term memory: last 3 turns

    # ---------------------------------------------------------------- LLM
    def interpret_request(self, request, hours, tasks, allow_llm=True):
        """LLM interpretation with strict validation and a safe fallback."""
        fallback = rule_based_interpretation(request, tasks)
        if not allow_llm:
            return {**fallback, "llm_status": "guardrail_skip"}
        if not request.strip():
            return {**fallback, "llm_status": "skipped_empty"}
        if not (self.use_llm and allow_llm):
            return {**fallback, "llm_status": "disabled"}

        subjects = sorted({t["subject"] for t in tasks if t["subject"]})
        prompt = (
            "You classify a student's study-planning request. Return ONLY JSON with keys "
            f'"intent" (one of {INTENTS}) and "focus" (a short phrase). '
            "Use focus_subject only if the request names one of these known subjects/tasks: "
            f"{subjects}. Never invent tasks, subjects or hours.\n"
            f"Request: {request}\nAvailable hours: {hours:g}")
        try:
            resp = requests.post(self.url, json={
                "model": self.model, "stream": False, "format": "json", "think": False,
                "messages": [{"role": "system", "content": "Extract intent and focus. Output JSON only."},
                             {"role": "user", "content": prompt}],
                "options": {"temperature": 0.1}}, timeout=(2, 45))
            resp.raise_for_status()
            parsed = _parse_llm_json(resp.json()["message"]["content"])
            intent = str(parsed.get("intent", ""))
            if intent not in INTENTS:                      # validate against allow-list
                return {**fallback, "llm_status": "invalid_intent"}
            raw = parsed.get("suggested_tools", [])
            suggested = [t for t in (raw if isinstance(raw, list) else []) if t in TOOL_REGISTRY]
            return {"intent": intent, "focus": str(parsed.get("focus", DEFAULT_FOCUS))[:80],
                    "suggested_tools": suggested, "llm_status": "ok"}
        except requests.RequestException:
            return {**fallback, "llm_status": "offline"}
        except (ValueError, KeyError, TypeError):
            return {**fallback, "llm_status": "invalid_response"}

    def coach_note(self, plan, hours, budget, risks, intent):
        """LLM writes a short, friendly explanation of the plan (generative step).

        Grounding guard: every number in the note must already appear in the facts we gave
        the model; otherwise the note is rejected and the deterministic explanation is used."""
        facts = {"intent": intent, "available_hours": hours, "budget_hours": budget,
                 "plan": [{"task": p["Task"], "hours": p["Planned Hours"], "deadline": p["Deadline"],
                           "why": p["Why"]} for p in plan],
                 "needs_attention": [r["Task"] for r in risks if r["Status"] != "On track"]}
        facts_json = json.dumps(facts)
        prompt = ("You are a supportive study coach. Write 2-3 short sentences about the plan below. "
                  "Use ONLY the facts given. Do not mention any number that is not in the facts, "
                  "do not add tasks, and do not give medical or academic-integrity advice.\n"
                  f"Facts: {facts_json}")
        try:
            resp = requests.post(self.url, json={
                "model": self.model, "stream": False, "think": False,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.3}}, timeout=(2, 60))
            resp.raise_for_status()
            text = re.sub(r"<think>.*?</think>", "", resp.json()["message"]["content"], flags=re.S).strip()
        except requests.RequestException:
            return None, "offline"
        except (ValueError, KeyError, TypeError):
            return None, "invalid_response"
        if not text or len(text) > 600:
            return None, "rejected_length"
        if not _numbers(text) <= _numbers(facts_json):
            return None, "rejected_ungrounded"
        return text, "ok"

    # ------------------------------------------------------------ main loop
    def run(self, request, default_hours, tasks, feedback_hist=None, past_runs=None,
            today=None, fail_tools=()):
        """Pure agent loop (no database access) so it can be evaluated repeatably."""
        t_start = time.perf_counter()
        today = today or date.today()
        feedback_hist = feedback_hist or []
        past_runs = past_runs or []
        trace, warnings = [], []

        def step(name, t0, **data):
            trace.append({"step": name, "ms": round((time.perf_counter() - t0) * 1000, 2), **data})

        # 1. perception + guardrails
        t0 = time.perf_counter()
        guard = check_request(request)
        step("1 perception & guardrails", t0, status=guard["status"], flags=guard["flags"],
             input=guard["clean"] or "(empty)")
        if guard["status"] == "blocked":
            return self._blocked(guard, trace, t_start, default_hours)
        if guard["message"]:
            warnings.append(guard["message"])
        clean = guard["clean"]

        # 2. time extraction (+ short-term memory for follow-ups)
        t0 = time.perf_counter()
        hours, source = extract_hours(clean, default_hours)
        if source == "form" and self.short_term and re.search(r"\b(same|again|instead|but)\b", clean.lower()):
            hours, source = self.short_term[-1]["hours"], "short-term memory"
        hours, warn = clamp_hours(hours)
        if warn:
            warnings.append(warn)
        step("2 time extraction", t0, hours=hours, source=source)

        # 3. interpretation (LLM or fallback)
        t0 = time.perf_counter()
        interp = self.interpret_request(clean, hours, tasks, allow_llm=guard["llm_allowed"])
        step("3 request interpretation", t0, **interp)
        intent = interp["intent"]

        # 4. tool selection (policy, not the LLM)
        t0 = time.perf_counter()
        subj_ids = subject_match_tool(clean, tasks) if intent == "focus_subject" or clean else []
        selected = select_tools(clean, intent, subject_hit=bool(subj_ids))
        for name in interp.get("suggested_tools", []):        # LLM may suggest; policy validated it above
            if name in TOOL_REGISTRY and name not in {x["tool"] for x in selected}:
                selected.append({"tool": name, "reason": "Suggested by the LLM and validated against the tool registry."})
        tool_names = [s["tool"] for s in selected]
        step("4 tool selection", t0, selected=selected)

        # 5. memory retrieval (tasks, feedback, episodic runs)
        t0 = time.perf_counter()
        pending = [t for t in tasks if t["status"] == "Pending"]
        boosts = self._starvation_boosts(pending, past_runs)
        fb_types = [f["feedback_type"] if isinstance(f, dict) else f for f in feedback_hist]
        step("5 memory retrieval", t0, pending_tasks=len(pending), recent_feedback=fb_types[:3],
             past_runs_used=len(past_runs[:5]), boosted_tasks=len(boosts))

        # 6. tool execution (each wrapped so failures degrade gracefully)
        t0 = time.perf_counter()
        tool_log, candidate_ids, risks, score_fn = [], None, [], task_priority_tool
        if "subject_match_tool" in tool_names:
            r = run_tool("subject_match_tool", subject_match_tool, clean, tasks, fail_tools=fail_tools)
            tool_log.append({k: r[k] for k in ("tool", "ok", "error", "ms")})
            if r["ok"] and r["result"]:
                for tid in r["result"]:
                    boosts[tid] = boosts.get(tid, 0) + 2.0      # focus subject first, others fill the rest
            elif not r["ok"]:
                warnings.append("Subject matching failed; the plan uses general priority instead.")
        if "deadline_risk_tool" in tool_names:
            r = run_tool("deadline_risk_tool", deadline_risk_tool, tasks, today, fail_tools=fail_tools)
            tool_log.append({k: r[k] for k in ("tool", "ok", "error", "ms")})
            if r["ok"]:
                risks = r["result"]
            else:
                warnings.append("Deadline-risk check failed, so risk warnings are unavailable.")
        if intent == "urgent_only":
            urgent = [t["id"] for t in pending if (date.fromisoformat(t["deadline"]) - today).days <= 3]
            high = [t["id"] for t in pending if t["priority"] == "High"]
            candidate_ids = set(urgent) or set(high) or None
            if candidate_ids is None:
                warnings.append("No urgent tasks were found, so all pending tasks were considered.")
        if "task_priority_tool" in tool_names:
            probe = run_tool("task_priority_tool", task_priority_tool,
                             pending[0], today, 0.0, fail_tools=fail_tools) if pending else {"ok": True, "ms": 0, "error": None}
            tool_log.append({"tool": "task_priority_tool", "ok": probe["ok"], "error": probe["error"], "ms": probe["ms"]})
            if not probe["ok"]:                                  # degraded mode: nearest deadline first
                score_fn = lambda t, td, b=0.0: -(date.fromisoformat(t["deadline"]) - td).days + b
                warnings.append("Priority tool failed; fell back to ordering by nearest deadline.")
        if "study_time_tool" in tool_names:
            r = run_tool("study_time_tool", study_time_tool, pending, fail_tools=fail_tools)
            tool_log.append({k: r[k] for k in ("tool", "ok", "error", "ms")})
        step("6 tool execution", t0, tools=tool_log)

        # 7. planning + feedback adaptation
        t0 = time.perf_counter()
        if intent == "workload_review":
            planned = make_plan(tasks, 0.0, fb_types, today, boosts, score_fn=score_fn)
            planned.update(plan=[], budget=0.0, adaptation="Workload review only; no study time was allocated.")
            planned["factor"] = 1.0
        else:
            planned = make_plan(tasks, hours, fb_types, today, boosts, candidate_ids, score_fn)
        plan = planned["plan"]
        step("7 planning & adaptation", t0, plan_items=len(plan), budget=planned["budget"],
             budget_factor=planned["factor"], note=planned["adaptation"])

        # 8. reflection: the agent verifies its own output before returning it
        t0 = time.perf_counter()
        reflection = self._reflect(plan, planned["budget"], tasks)
        if not all(c["passed"] for c in reflection):
            keep, used = [], 0.0
            ids = {t["id"]: t for t in pending}
            for p in plan:
                if p["_id"] in ids and used + p["Planned Hours"] <= planned["budget"] + 1e-6:
                    keep.append(p)
                    used += p["Planned Hours"]
            plan = keep
            warnings.append("Self-check found a problem in the draft plan; it was repaired automatically.")
        step("8 reflection (self-check)", t0, checks=reflection)

        # 8b. LLM coach note (only when the LLM answered step 3; grounded and optional)
        t0 = time.perf_counter()
        note, note_status = None, "not_used"
        if interp["llm_status"] == "ok" and (plan or intent == "workload_review"):
            note, note_status = self.coach_note(plan, hours, planned["budget"], risks, intent)
        step("8b LLM coach note (grounded)", t0, status=note_status)

        # 9. action / result
        latency = round((time.perf_counter() - t_start) * 1000, 2)
        public_plan = [{k: v for k, v in p.items() if k != "_id"} for p in plan]
        explanation = self._explain(interp, hours, source, planned, intent, len(plan), risks)
        trace.append({"step": "9 action / result", "result": "Plan returned for user review", "total_ms": latency})
        self.short_term.append({"request": clean, "intent": intent, "hours": hours})

        return {"blocked": False, "mode": intent, "plan": public_plan, "explanation": explanation,
                "trace": trace, "available_hours": hours, "planning_budget": planned["budget"],
                "budget_factor": planned["factor"], "intent": intent, "focus": interp["focus"],
                "llm_status": interp["llm_status"], "tools_used": tool_names, "tool_log": tool_log,
                "risks": risks, "warnings": warnings, "reflection": reflection,
                "total_pending_hours": planned["total_pending_hours"],
                "excluded_ids": planned["excluded_ids"], "latency_ms": latency, "clean_request": clean,
                "llm_note": note, "llm_note_status": note_status}

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _starvation_boosts(pending, past_runs):
        """Episodic memory: tasks left out of recent plans get a growing score boost."""
        misses = {}
        for run in past_runs[:5]:
            for tid in run.get("excluded_ids", []):
                misses[tid] = misses.get(tid, 0) + 1
        return {t["id"]: min(1.5, 0.5 * misses[t["id"]]) for t in pending if misses.get(t["id"])}

    @staticmethod
    def _reflect(plan, budget, tasks):
        by_id = {t["id"]: t for t in tasks}
        total = sum(p["Planned Hours"] for p in plan)
        ids = [p["_id"] for p in plan]
        checks = [
            {"check": "Total planned time within budget", "passed": total <= budget + 1e-6},
            {"check": "Only pending tasks scheduled", "passed": all(by_id.get(i, {}).get("status") == "Pending" for i in ids)},
            {"check": "Every task exists in memory (no invented tasks)", "passed": all(i in by_id for i in ids)},
            {"check": "No task scheduled twice", "passed": len(ids) == len(set(ids))},
            {"check": "No task given more hours than estimated",
             "passed": all(p["Planned Hours"] <= float(by_id[p["_id"]]["study_hours"]) + 1e-6 for p in plan if p["_id"] in by_id)},
        ]
        return checks

    @staticmethod
    def _explain(interp, hours, source, planned, intent, n_items, risks):
        parts = [f"Request understood as '{intent}' (focus: {interp['focus']}).",
                 f"Available time: {hours:g}h (from {source}).",
                 f"Pending workload: {planned['total_pending_hours']:g}h.",
                 f"Planning budget: {planned['budget']:g}h. {planned['adaptation']}"]
        if intent == "workload_review":
            flagged = sum(r["Status"] != "On track" for r in risks)
            parts.append(f"{flagged} of {len(risks)} pending task(s) need attention.")
        else:
            parts.append(f"{n_items} task(s) scheduled.")
        status = interp["llm_status"]
        if status in ("offline", "invalid_response", "invalid_intent"):
            parts.append("The local LLM was unavailable or returned invalid output, so the rule-based interpreter was used.")
        elif status == "ok":
            parts.append("Request interpreted by the local LLM; all numbers come from Python tools.")
        return " ".join(parts)

    @staticmethod
    def _blocked(guard, trace, t_start, hours):
        trace.append({"step": "9 action / result", "result": "Request refused by guardrail"})
        return {"blocked": True, "mode": "blocked", "plan": [], "explanation": guard["message"],
                "trace": trace, "available_hours": hours, "planning_budget": 0.0, "budget_factor": 1.0,
                "intent": "blocked", "focus": "", "llm_status": "not_called", "tools_used": [], "tool_log": [],
                "risks": [], "warnings": [guard["message"]], "reflection": [], "total_pending_hours": 0.0,
                "excluded_ids": [], "latency_ms": round((time.perf_counter() - t_start) * 1000, 2),
                "clean_request": guard["clean"], "llm_note": None, "llm_note_status": "not_used"}

    # --------------------------------------------------- database wrapper
    def plan(self, request, available_hours):
        """Run the loop against the persistent memory and log the episode."""
        tasks = memory.get_tasks()
        fb = memory.feedback_history(3)
        runs = memory.recent_runs(5)
        result = self.run(request, available_hours, tasks, fb, runs)
        if not result["blocked"]:
            result["run_id"] = memory.log_agent_run(
                result["clean_request"], result["available_hours"], ",".join(result["tools_used"]),
                result["explanation"], result["intent"], result["plan"], result["excluded_ids"],
                result["latency_ms"], result["llm_status"])
        return result
