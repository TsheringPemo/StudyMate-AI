# Milestones and Git evidence

The assignment asks for a Git history that shows progressive development. **Make real commits as you work and
understand each one** - do not fake dates. If you are submitting now, commit in the milestone order below
(each commit adds the files listed) so the history reflects how the system is built up.

| Milestone | Files to commit together | Commit message |
|---|---|---|
| 1 Problem & architecture (Wk 2) | README.md, docs/figures/architecture.png | `docs: problem, PEAS and architecture` |
| 2 Planning & tools (Wk 4) | tools.py, scheduler.py | `feat: tools, tool-selection policy, scheduler` |
| 3 Learning & adaptation (Wk 6) | memory.py | `feat: SQLite memory, feedback reward, episodic log` |
| 5 LLM & knowledge (Wk 11) | agent.py | `feat: agent loop, Ollama interpreter with fallback, reflection` |
| 6 Evaluation & safety (Wk 13-14) | guardrails.py, evaluation.py, generate_assets.py | `feat: guardrails and 70-case evaluation` |
| Final integration (Wk 15) | app.py, requirements.txt, docs/ | `feat: Streamlit UI, report and demo guide` |

Milestone 4 (multi-agent) is intentionally skipped: a single agent is justified because the task has one goal and one
shared state (see report, section 3).

Quick start:
```
git init
git add README.md docs/figures/architecture.png && git commit -m "docs: problem, PEAS and architecture"
git add tools.py scheduler.py && git commit -m "feat: tools, tool-selection policy, scheduler"
git add memory.py && git commit -m "feat: SQLite memory, feedback reward, episodic log"
git add agent.py && git commit -m "feat: agent loop, Ollama interpreter with fallback, reflection"
git add guardrails.py evaluation.py generate_assets.py && git commit -m "feat: guardrails and 70-case evaluation"
git add -A && git commit -m "feat: Streamlit UI, report and demo guide"
```
