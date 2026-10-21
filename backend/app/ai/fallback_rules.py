"""Deterministic fallback used only when Gemini is not configured. Results are labeled source='rules'."""
import re

from app.ai.schemas import ConversationAnalysis, UtteranceDecision
from app.services.commitment_detector import _DUE, _HEDGE, _NEGATION, detect_commitment

_ACCEPT = re.compile(
    r"^\s*(?:yes|yeah|yep|yup|sure|ok(?:ay)?|of course|absolutely|definitely|will do|on it|deal|done|"
    r"no problem|sounds good|count me in|i can do that|i got it|got it|consider it done|you got it)\b",
    re.IGNORECASE,
)
_REQUEST = re.compile(r"\b(?:can|could|would|will)\s+you\s+(?:please\s+)?(.+?)\??$", re.IGNORECASE)
_DEFER = re.compile(
    r"\b(?:let me (?:see|check|think|know)|get back to you|need to (?:talk|check|ask|think)|i'll try|"
    r"take you up|think about it|tentativ|we'll see|let's see)\b", re.IGNORECASE)
_PLEASE = re.compile(r"^\s*please\s+(.+?)[.!?]?$", re.IGNORECASE)


def _request_action(text: str) -> str | None:
    text = text.replace("\u2019", "'").strip()
    for sentence in reversed(re.split(r"(?<=[.!?])\s+", text)):
        m = _REQUEST.search(sentence) or _PLEASE.search(sentence)
        if m:
            return m.group(1).strip(" ?.!,")
    return None


def analyze_with_rules(conversation: dict) -> ConversationAnalysis:
    user = conversation["user_speaker"]
    lines = conversation["utterances"]
    others = tuple(sorted({u["speaker"] for u in lines if u["speaker"] != user}))
    decisions: list[UtteranceDecision] = []
    for i, u in enumerate(lines):
        if u["speaker"] != user:
            continue
        if _DEFER.search(u["text"].replace("\u2019", "'")) or _HEDGE.search(u["text"]):
            continue
        found = detect_commitment(u["text"], others)
        if found:
            decisions.append(UtteranceDecision(
                utterance_sequence=u["sequence"], label="commitment", action_text=found.action_text[:1].upper() + found.action_text[1:],
                counterparty=found.counterparty, due_text=found.due_text, confidence=min(found.confidence, 0.85),
                explanation="Rules fallback: the line uses explicit promise wording.", evidence_quote=u["text"]))
            continue
        prev = next((p for p in reversed(lines[:i]) if p["speaker"] != user), None)
        text = u["text"].replace("\u2019", "'")
        if prev and _ACCEPT.search(text) and not text.rstrip().endswith("?") and not (_HEDGE.search(text) or _NEGATION.search(text)):
            action = _request_action(prev["text"])
            if action and len(action.split()) >= 2:
                due = _DUE.search(action)
                due_text = due.group(0).strip() if due else None
                if due:
                    action = re.sub(r"\s+", " ", f"{action[:due.start()]} {action[due.end():]}").strip(" ,")
                action = re.sub(r"\bme\b", prev["speaker"], action)
                decisions.append(UtteranceDecision(
                    utterance_sequence=u["sequence"], label="commitment", action_text=action[:1].upper() + action[1:],
                    counterparty=prev["speaker"], due_text=due_text, confidence=0.6,
                    explanation=f"Rules fallback: the user accepted {prev['speaker']}'s request.", evidence_quote=u["text"]))
    summary = f"Rules fallback reviewed {sum(1 for u in lines if u['speaker'] == user)} line(s) from {user}."
    return ConversationAnalysis(summary=summary, has_commitment=bool(decisions), decisions=decisions)
