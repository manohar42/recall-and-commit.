import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_PART = r"(?:\s+(?:morning|afternoon|evening|night))?"

_SENTENCES = re.compile(r"(?<=[.!?])\s+")
_NEGATION = re.compile(r"\b(?:i\s+won't|i\s+will\s+not|i\s+will\s+never|i\s+can't|i\s+cannot)\b", re.IGNORECASE)
_HEDGE = re.compile(r"\b(?:maybe|might|perhaps|probably|possibly|i\s+think\s+i)\b", re.IGNORECASE)

# (pattern, base confidence), strongest first
_TRIGGERS = [
    (re.compile(r"\bi\s+promise(?:\s+to)?\b", re.IGNORECASE), 0.90),
    (re.compile(r"\bi\s+will\b", re.IGNORECASE), 0.80),
    (re.compile(r"\bi'll\b", re.IGNORECASE), 0.80),
    (re.compile(r"\bi(?:'m|\s+am)\s+going\s+to\b", re.IGNORECASE), 0.70),
    (re.compile(r"\blet\s+me\b", re.IGNORECASE), 0.60),
    (re.compile(r"\bi\s+can\s+(?=(?:send|share|get|bring|prepare|follow|check|review|call|email)\b)", re.IGNORECASE), 0.60),
]

_DUE = re.compile(
    rf"\b(?:(?:by|before|on|until)\s+)?(?:(?:next|this)\s+)?"
    rf"(?:(?:{'|'.join(_DAYS)}){_PART}"
    rf"|tomorrow{_PART}|tonight|today"
    rf"|end\s+of\s+(?:the\s+)?(?:day|week|month)"
    rf"|next\s+week|next\s+month|this\s+week)\b",
    re.IGNORECASE,
)


@dataclass
class DetectedCommitment:
    action_text: str
    due_text: str | None
    counterparty: str | None
    confidence: float


def detect_commitment(text: str, other_speakers: tuple[str, ...] = ()) -> DetectedCommitment | None:
    """Return the first likely commitment in the text, or None."""
    text = text.replace("\u2019", "'").strip()

    for sentence in _SENTENCES.split(text):
        s = sentence.strip()
        if not s or s.endswith("?"):
            continue
        if _NEGATION.search(s) or _HEDGE.search(s):
            continue

        for pattern, base in _TRIGGERS:
            m = pattern.search(s)
            if not m:
                continue

            rest = s[m.end():].strip()
            due = _DUE.search(rest)
            due_text = due.group(0).strip() if due else None
            if due:
                rest = f"{rest[:due.start()]} {rest[due.end():]}"
            action = re.sub(r"\s+", " ", rest).strip(" .,!;:-")
            if len(action.split()) < 2:
                continue

            counterparty = None
            named = re.search(r"\b(?:to|with|for)\s+([A-Z][a-z]+)\b", action)
            if named:
                counterparty = named.group(1)
            elif re.search(r"\byou\b", action, re.IGNORECASE) and len(other_speakers) == 1:
                counterparty = other_speakers[0]

            confidence = min(0.99, base + (0.10 if due_text else 0.0))
            return DetectedCommitment(action, due_text, counterparty, round(confidence, 2))

    return None


def parse_due(due_text: str | None, reference: datetime | None, tz_name: str = "America/Phoenix") -> datetime | None:
    """Resolve a due phrase relative to when it was said (in the user's timezone). None if ambiguous."""
    if not due_text or reference is None:
        return None
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(tz_name)
    local = reference.astimezone(zone) if reference.tzinfo else reference.replace(tzinfo=zone)
    t = due_text.lower()
    hour = 17
    if "morning" in t:
        hour = 9
    elif "evening" in t or "tonight" in t or "night" in t:
        hour = 20

    day = local.date()
    if "tomorrow" in t:
        day += timedelta(days=1)
    elif "next week" in t:
        day += timedelta(days=7 - local.weekday())
    elif "end of the week" in t or "end of week" in t or "this week" in t:
        day += timedelta(days=(4 - local.weekday()) % 7)
    elif not ("today" in t or "tonight" in t or "end of day" in t or "end of the day" in t):
        weekday = next((i for i, name in enumerate(_DAYS) if name in t), None)
        if weekday is None:
            return None
        ahead = (weekday - local.weekday()) % 7 or 7
        day += timedelta(days=ahead)

    return datetime.combine(day, time(hour), tzinfo=zone).astimezone(timezone.utc)
