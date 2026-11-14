"""Safety guardrails for StudyMate (DAT404 Milestone 6 / Week 14).

The guardrails run BEFORE any LLM call. They are deliberately simple, transparent
rules so they can be tested and explained in the defence.

Least-privilege design: the agent can only read tasks and propose a plan. It has
no tool that deletes, edits or submits anything, so even a successful prompt
injection cannot cause a harmful action - at worst it is ignored.
"""
import re

MAX_REQUEST_CHARS = 500
MIN_HOURS = 0.5
MAX_HOURS = 16.0

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above|your) (instructions|rules)",
    r"(reveal|show|print|repeat) (your |the )?(system|hidden) (prompt|instructions)",
    r"you are now\b",
    r"act as (an? )?(unrestricted|different|new)",
    r"\bjailbreak\b",
    r"delete (all|every|my) (tasks?|data|records?)",
    r"drop table",
]

# Academic-integrity patterns: asking the agent to DO the work, not plan it.
_LEAD = r"(?:^|[.!?]\s+|please\s+|can you\s+|could you\s+|just\s+|you\s+|help me\s+|and\s+)"
INTEGRITY_PATTERNS = [
    _LEAD + r"(?:write|do|complete|solve|finish|answer)\s+(?:my|the|this)\s+"
            r"(?:\w+\s+){0,2}(?:essay|assignment|homework|exam|quiz|report|thesis|code|project)\b",
    r"\b(?:write|do|complete|solve|finish|answer)\b[^.]{0,40}\bfor me\b",
    r"\bcheat\b",
]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)")


def redact_pii(text):
    """Replace e-mail addresses and phone numbers; return (text, found_bool)."""
    out = EMAIL_RE.sub("[email removed]", text)
    out = PHONE_RE.sub("[number removed]", out)
    return out, out != text


def check_request(request):
    """Validate a free-text request.

    Returns a dict:
      status  : "ok" | "sanitised" | "blocked"
      flags   : list of short machine-readable flags
      clean   : request text that is safe to log / send to the LLM
      message : human-readable explanation when something was changed/blocked
      llm_allowed : False when the text must not be sent to the LLM
    """
    text = (request or "").strip()
    flags, notes = [], []
    llm_allowed = True

    if len(text) > MAX_REQUEST_CHARS:
        text = text[:MAX_REQUEST_CHARS]
        flags.append("truncated")
        notes.append(f"Request was longer than {MAX_REQUEST_CHARS} characters and was shortened.")

    lowered = text.lower()

    for pat in INTEGRITY_PATTERNS:
        if re.search(pat, lowered):
            return {
                "status": "blocked", "flags": flags + ["academic_integrity"], "clean": text,
                "llm_allowed": False,
                "message": ("StudyMate plans your study time; it does not complete assignments, "
                            "exams or other graded work for you. Ask for a study plan instead, "
                            "for example: 'I have 3 hours, help me plan my report'."),
            }

    for pat in INJECTION_PATTERNS:
        if re.search(pat, lowered):
            flags.append("prompt_injection")
            notes.append("Instruction-like text in the request was ignored; a default plan was used.")
            llm_allowed = False
            text = ""          # discard the suspicious content entirely
            break

    text, pii = redact_pii(text)
    if pii:
        flags.append("pii_redacted")
        notes.append("Personal contact details were removed from the request before processing.")

    return {
        "status": "sanitised" if flags else "ok", "flags": flags, "clean": text,
        "llm_allowed": llm_allowed, "message": " ".join(notes),
    }


def clamp_hours(hours):
    """Keep study time inside a realistic range. Returns (hours, warning_or_None)."""
    hours = float(hours)
    if hours > MAX_HOURS:
        return MAX_HOURS, f"Requested {hours:g}h exceeds the {MAX_HOURS:g}h daily maximum; using {MAX_HOURS:g}h."
    if hours < MIN_HOURS:
        return MIN_HOURS, f"Requested time is below the {MIN_HOURS:g}h minimum; using {MIN_HOURS:g}h."
    if hours > 10:
        return hours, "Plans over 10 hours are hard to sustain - schedule real breaks and sleep."
    return hours, None


def clean_task_text(value, max_len=120):
    """Sanitise task names/subjects typed into forms (trim, collapse spaces, cap length)."""
    value = re.sub(r"\s+", " ", (value or "")).strip()
    return value[:max_len]
