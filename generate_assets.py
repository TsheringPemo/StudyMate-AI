"""Generate the figures used in the report: python generate_assets.py"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from evaluation import run_evaluation, INTENT_CASES
from agent import INTENTS
from scheduler import budget_factor

OUT = Path(__file__).parent / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
BROWN, TAN, CREAM, GREEN, RED = "#6B4F3A", "#C9A98A", "#F5EDE0", "#5B8C5A", "#B5473A"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})


def box(ax, x, y, w, h, text, fc=CREAM, ec=BROWN, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color="#3E342B")


def arrow(ax, x1, y1, x2, y2, style="-|>"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle=style, color=BROWN, lw=1.5))


def architecture():
    fig, ax = plt.subplots(figsize=(12, 7.4))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7.7); ax.axis("off")
    box(ax, 0.2, 5.9, 1.9, 1.0, "Student\n(Streamlit UI)", fc=TAN, bold=True)
    steps = ["1 Perception &\nGuardrails", "2 Time\nextraction", "3 Request\ninterpretation", "4 Tool\nselection policy",
             "5 Memory\nretrieval", "6 Tool\nexecution", "7 Planning &\nadaptation", "8 Reflection +\nLLM coach note"]
    xs = [2.6, 4.45, 6.3, 8.15]
    for i, s in enumerate(steps):
        x = xs[i % 4]; y = 5.9 if i < 4 else 4.1
        if i >= 4: x = xs[3 - (i - 4)]
        box(ax, x, y, 1.65, 1.0, s, fc="white", bold=True, fs=8.5)
    for i in range(3): arrow(ax, xs[i] + 1.65, 6.4, xs[i + 1], 6.4)
    arrow(ax, xs[3] + .8, 5.9, xs[3] + .8, 5.1)
    for i in range(3): arrow(ax, xs[3 - i], 4.6, xs[2 - i] + 1.65, 4.6)
    arrow(ax, 2.1, 6.4, 2.6, 6.4)
    box(ax, 10.2, 5.9, 1.6, 1.0, "Local LLM\n(Ollama qwen3:8b)\nintent, tools, note\n(all validated)", fc="#EFE2F5", ec="#6B3F8A", fs=7.5)
    ax.plot([7.1, 7.1, 11.0], [6.9, 7.1, 7.1], color=BROWN, lw=1.5)
    arrow(ax, 11.0, 7.1, 11.0, 6.9, "<|-|>")
    box(ax, 0.2, 4.1, 1.9, 1.0, "9 Action / Result\nplan + explanation", fc=TAN, bold=True, fs=8.5)
    arrow(ax, xs[0], 4.6, 2.1, 4.6)
    arrow(ax, 1.15, 4.1, 1.15, 3.5)
    box(ax, 0.2, 2.5, 1.9, 0.95, "Student feedback\n(reward score)", fc="#E4EFE0", ec=GREEN, bold=True, fs=8.5)
    # memory + tools layer
    box(ax, 2.6, 0.4, 4.4, 2.5, "", fc="#FBF6EE")
    ax.text(4.8, 2.62, "SQLite memory", ha="center", fontweight="bold", fontsize=10, color=BROWN)
    box(ax, 2.8, 1.65, 1.3, 0.75, "tasks\n(semantic)", fs=8); box(ax, 4.2, 1.65, 1.3, 0.75, "feedback\n+ reward", fs=8)
    box(ax, 5.6, 1.65, 1.2, 0.75, "agent_runs\n(episodic)", fs=8)
    ax.text(4.8, 1.2, "short-term memory: last 3 turns (in agent)", ha="center", fontsize=8, style="italic")
    ax.text(4.8, 0.7, "Read in steps 5 and 7  |  Written after each run and feedback", ha="center", fontsize=8)
    box(ax, 7.4, 0.4, 4.4, 2.5, "", fc="#FBF6EE")
    ax.text(9.6, 2.62, "Python tools (deterministic)", ha="center", fontweight="bold", fontsize=10, color=BROWN)
    for i, t in enumerate(["task_priority_tool", "study_time_tool", "deadline_risk_tool", "subject_match_tool"]):
        box(ax, 7.6 + (i % 2) * 2.1, 1.65 - (i // 2) * 0.0 if i < 2 else 0.65, 1.95, 0.75, t, fs=8)
    arrow(ax, 4.8, 2.9, 5.3, 4.1); arrow(ax, 6.5, 2.9, 8.5, 4.1); arrow(ax, 9.6, 2.9, 7.3, 4.1)
    ax.text(6.0, 7.5, "StudyMate AI - single tool-using agent with guardrails, memory, feedback adaptation and reflection",
            ha="center", fontsize=11, fontweight="bold", color=BROWN)
    fig.savefig(OUT / "architecture.png", dpi=170, bbox_inches="tight", facecolor="white"); plt.close(fig)


def eval_charts(rows, s):
    # 1 pass rate by group
    groups = list(s["by_group"]); rates = [s["by_group"][g]["rate"] * 100 for g in groups]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(groups, rates, color=[GREEN if r == 100 else RED for r in rates])
    for b, g in zip(bars, groups):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{s['by_group'][g]['passed']}/{s['by_group'][g]['total']}", ha="center", fontsize=9)
    ax.set_ylim(0, 115); ax.set_ylabel("% of tests passed"); ax.set_title("Evaluation results by test group")
    plt.xticks(rotation=20); fig.tight_layout(); fig.savefig(OUT / "eval_by_group.png", dpi=160); plt.close(fig)
    # 2 confusion matrix
    m = s["confusion_matrix"]; fig, ax = plt.subplots(figsize=(5.6, 4.6))
    data = [[m[i][j] for j in INTENTS] for i in INTENTS]
    ax.imshow(data, cmap="YlOrBr")
    ax.set_xticks(range(len(INTENTS))); ax.set_yticks(range(len(INTENTS)))
    ax.set_xticklabels(INTENTS, rotation=30, ha="right", fontsize=8); ax.set_yticklabels(INTENTS, fontsize=8)
    for i in range(len(INTENTS)):
        for j in range(len(INTENTS)): ax.text(j, i, data[i][j], ha="center", va="center", fontsize=11)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Expected"); ax.set_title("Intent classification (rule-based)")
    fig.tight_layout(); fig.savefig(OUT / "confusion_matrix.png", dpi=160); plt.close(fig)
    # 3 tool usage
    tc = s["tool_counts"]; fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.barh(list(tc), list(tc.values()), color=BROWN); ax.set_xlabel("Times selected in tool-selection test cases")
    ax.set_title("Tool-usage frequency"); fig.tight_layout(); fig.savefig(OUT / "tool_usage.png", dpi=160); plt.close(fig)
    # 4 latency
    fig, ax = plt.subplots(figsize=(7, 3.6)); ax.hist(s["latency_ms"]["samples"], bins=12, color=TAN, edgecolor=BROWN)
    ax.axvline(s["latency_ms"]["mean"], color=RED, ls="--", label=f"mean {s['latency_ms']['mean']:.2f} ms")
    ax.set_xlabel("Latency per agent run (ms, 40 tasks, LLM off)"); ax.set_ylabel("Runs"); ax.legend()
    ax.set_title("Planning latency"); fig.tight_layout(); fig.savefig(OUT / "latency.png", dpi=160); plt.close(fig)


def adaptation_chart():
    seq = ["Helpful", "Too much work", "Too much work", "Helpful", "Helpful", "Too little work", "Too difficult", "Helpful"]
    budgets, hist = [], []
    for f in seq:
        hist.insert(0, f); budgets.append(4 * budget_factor(hist))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(1, len(seq) + 1), budgets, marker="o", color=BROWN, lw=2)
    for i, f in enumerate(seq): ax.annotate(f.replace(" ", "\n"), (i + 1, budgets[i]), textcoords="offset points", xytext=(0, -30), ha="center", fontsize=7)
    ax.axhline(4, color="grey", ls=":", label="entered time (4 h)"); ax.set_ylim(1.5, 4.5)
    ax.set_xlabel("Feedback interaction"); ax.set_ylabel("Planning budget for 4 h entered (h)")
    ax.set_title("Adaptive budget after each feedback"); ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(OUT / "adaptation.png", dpi=160); plt.close(fig)
    return list(zip(seq, [round(b, 2) for b in budgets]))


if __name__ == "__main__":
    rows, summary = run_evaluation()
    architecture(); eval_charts(rows, summary); print(adaptation_chart())
    print("Figures written to", OUT)
