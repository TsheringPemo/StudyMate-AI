# StudyMate AI - a tool-using study-planning agent

DAT404 Intelligent and Generative Agents - Assignment D (30 %).

StudyMate helps a student decide **what to study in the time they actually have**. It reads a free-text
request, chooses tools, checks deadlines, remembers past plans and feedback, adapts its time budget, checks its
own plan and returns a ranked, explained study plan for the student to review.

> **Not a chatbot.** The LLM interprets the request, suggests tools and writes a short coach note - each output is
> validated by code. Ranking, hours, risk checks and adaptation are done by deterministic Python tools, so the plan
> cannot be hallucinated.

## Using the LLM
See **`docs/OLLAMA_SETUP.md`** for step-by-step setup (Ollama + `qwen3:8b`, or `qwen3:4b` for slower laptops).
The Study Planner shows *LLM status* and a *Coach note* when it works; if Ollama is off it simply uses the rule-based fallback.

## Agent loop

```
Student -> 1 Perception & guardrails -> 2 Time extraction -> 3 Interpretation (LLM or rules)
        -> 4 Tool-selection policy -> 5 Memory retrieval -> 6 Tool execution -> 7 Planning & adaptation
        -> 8 Reflection (self-check) -> 8b LLM coach note (grounded) -> 9 Action/Result -> Student feedback (reward) -> adapts next plan
```
Diagram: `docs/figures/architecture.png`. Every step is timed and shown in the app under **Agent trace**.

## Project layout

| File | Role |
|---|---|
| `app.py` | Streamlit UI (Dashboard, My Tasks, Study Planner, Feedback, Evaluation, About) |
| `agent.py` | Agent loop, LLM interpreter with fallback, reflection, tracing |
| `tools.py` | 4 tools + transparent tool-selection policy + safe tool runner |
| `scheduler.py` | Ranking, time-boxing, session splitting, feedback-based budget adaptation |
| `memory.py` | SQLite: tasks, feedback + reward, episodic run log (auto-migrates older databases) |
| `guardrails.py` | Input validation, prompt-injection, academic-integrity, PII and hour-limit guardrails |
| `evaluation.py` | 70 automated test cases in 8 groups (incl. LLM paths against a mock Ollama server) + metrics + known limitations |
| `generate_assets.py` | Produces the report figures from the evaluation results |
| `docs/` | Technical report, figures, demo/defence guide, milestone/Git guide |

## Tools

| Tool | Purpose |
|---|---|
| `task_priority_tool` | Score = priority weight + 5 x deadline urgency (+ memory boost) |
| `study_time_tool` | Total pending hours vs available time |
| `deadline_risk_tool` | Flags *Overdue* / *At risk* / *On track* using cumulative workload vs daily capacity |
| `subject_match_tool` | Grounds "study statistics" in real stored subjects/tasks (cannot invent tasks) |

The agent picks tools with an explicit policy (`tools.select_tools`) based on the interpreted intent and keywords,
and each call goes through `run_tool`, so a failing tool degrades the plan instead of crashing it.

## Memory and adaptation

* **Short-term**: last 3 turns (e.g. "same but only urgent" reuses the previous hours).
* **Semantic**: tasks table. **Episodic**: every run, including which tasks were left out.
  A task left out of recent plans gets a capped score boost (max +1.5) so it is not neglected forever.
* **Feedback -> reward**: Helpful +1, Too little -0.25, Too much / Too difficult -0.5.
* **Adaptation**: the planning budget = entered hours x factor, where factor comes from a weighted average of the last
  three feedback items (weights 0.5 / 0.3 / 0.2). One "Too much work" -> 75 %. Helpful/"Too little" recover it
  gradually. The factor never exceeds 100 %, so the agent never plans more than the time you entered.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# optional LLM interpretation (the app works without it)
ollama pull qwen3:8b
streamlit run app.py
```
macOS/Linux: `source .venv/bin/activate`. If Ollama is not running, *LLM status* shows "offline" and the
rule-based interpreter is used - planning still works.

Click **Load demo tasks** in the sidebar for sample data. Run tests with `python evaluation.py` or the Evaluation page.
Regenerate figures with `python generate_assets.py`.

## Evaluation summary (LLM off, repeatable)

70 test cases: Planner 12, Time parsing 9, Interpretation 10, Tool selection 6, Safety 10, Robustness 10,
LLM integration 12 (mock Ollama server: valid, malformed, invalid and hallucinated replies), Performance 1. Tool-selection accuracy and intent accuracy are measured separately; the mean run latency is
under 1 ms for 40 tasks (excluding the LLM). Three **known limitations** (e.g. "ninety minutes",
"1 hour and 30 minutes") are listed honestly and are not counted in the score. The LLM tests use a *mock* server, so they prove the agent handles good and bad LLM output correctly; they do
not measure how good Qwen3's answers are. See the report for method and failure analysis.

## Safety, privacy and limitations

* Guardrails run before the LLM: length cap (500 chars), prompt-injection neutralisation, academic-integrity
  refusal (the agent plans study time, it never does graded work), PII redaction, hours clamped to 0.5-16.
* Least privilege: the agent can only *read* tasks and *propose* a plan. It cannot delete, edit or submit anything.
* Data stays in the local SQLite file `data/studymate.db`; no cloud services are used.
* Limitations: keyword guardrails can be bypassed by paraphrase; scheduling ignores task difficulty, energy and
  breaks beyond a simple 90-minute block rule; hour estimates are the student's own; the feedback rule is a
  hand-designed heuristic, not learned; evaluation is functional, not a user study.

## Academic integrity / AI-assistance statement

AI coding assistance (Claude) was used to refactor and extend this project. The author is responsible for
understanding, testing and being able to explain all code. Libraries: Streamlit, pandas, requests,
matplotlib, SQLite (standard library), Ollama + Qwen3 (optional). Fill in your own Git history - see
`docs/MILESTONES_AND_GIT.md`.
