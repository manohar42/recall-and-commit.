"""LangGraph workflow for What If: gather context -> explain in a paragraph (Gemini) -> END.

Deterministic findings from services/planning.py stay authoritative; the AI only explains them.
"""
from datetime import timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.llm import AIError, get_chat_model, structured_call
from app.ai.schemas import WhatIfExplanation
from app.config import get_settings
from app.models_commitments import Commitment
from app.models_planning import CommitmentDependency
from app.services.timeutil import as_utc, format_local, format_range, parse_iso, utc_now

SYSTEM_PROMPT = """You are the What If planner for Recall & Commit. Write ONE clear paragraph (4-7 sentences)
for the user that explains: what the proposed task involves, which existing commitments fall on the same
day and when, any time conflicts or back-to-back transitions (no travel buffer), unresolved prerequisites,
and other issues (missing times, past dates, very long or late blocks). Treat the deterministic findings as
facts; do not contradict them and do not invent commitments. End with a practical suggestion (for example a
free slot or what to confirm). Remind the user nothing changes until they confirm. Set risk_level to
"conflict" if any time_conflict exists, "caution" for unknowns or tight transitions, otherwise "clear"."""


class WhatIfState(TypedDict, total=False):
    db: Any
    scenario: dict
    context: dict
    paragraph: str
    risk_level: str
    source: str
    error: str | None


def _span(c: Commitment):
    if c.starts_at and c.ends_at:
        return as_utc(c.starts_at), as_utc(c.ends_at)
    if c.due_at:
        return as_utc(c.due_at), as_utc(c.due_at)
    return None


def gather(state: WhatIfState) -> WhatIfState:
    db, sc = state["db"], state["scenario"]
    change = sc["proposed_change"]
    target = db.get(Commitment, sc["target_commitment_id"]) if sc.get("target_commitment_id") else None
    start, end = parse_iso(change.get("starts_at")), parse_iso(change.get("ends_at"))
    action = change.get("action_text") or (target.action_text if target else "the change")
    same_day, tight = [], []
    if start and end:
        window_a, window_b = start - timedelta(hours=14), end + timedelta(hours=14)
        for c in db.query(Commitment).filter(Commitment.status == "open").all():
            if target and c.id == target.id:
                continue
            span = _span(c)
            if not span or span[1] < window_a or span[0] > window_b:
                continue
            same_day.append({"id": c.id, "action": c.action_text, "when": format_range(span[0], span[1])
                             if span[0] != span[1] else f"due {format_local(span[0])}"})
            gap_before = (start - span[1]).total_seconds() / 60
            gap_after = (span[0] - end).total_seconds() / 60
            if 0 < gap_before < 45 or 0 < gap_after < 45:
                tight.append(f"'{c.action_text}' leaves only {int(min(x for x in (gap_before, gap_after) if x > 0))} minutes between tasks")
    deps = []
    if target:
        for d in db.query(CommitmentDependency).filter_by(dependent_id=target.id):
            pre = db.get(Commitment, d.prerequisite_id) if d.prerequisite_id else None
            deps.append(pre.action_text + f" ({pre.status})" if pre else (d.prerequisite_text or "external prerequisite"))
    issues = []
    if not (start and end):
        issues.append("No complete start and end time was given, so conflicts cannot be fully checked.")
    else:
        if end < utc_now():
            issues.append("The proposed time is already in the past.")
        hours = (end - start).total_seconds() / 3600
        if hours > 6:
            issues.append(f"The block is long ({hours:.1f} hours).")
    context = {"action": action, "operation": sc["operation"], "start": format_local(start) if start else None, "range": format_range(start, end) if start else None,
               "end": format_local(end) if end else None, "same_day": same_day, "tight": tight,
               "dependencies": deps, "issues": issues, "findings": sc["findings"]}
    return {"context": context, "error": None}


def route(state: WhatIfState) -> str:
    return "gemini_explain" if get_settings().ai_configured else "rules_explain"


def _render(ctx: dict) -> str:
    lines = [f"Proposed ({ctx['operation']}): {ctx['action']}", f"When: {ctx['start']} to {ctx['end']}", "",
             "Deterministic findings:"]
    lines += [f"- {f['type']}: {f['explanation']}" for f in ctx["findings"]] or ["- none"]
    lines += ["", "Open commitments near that time:"] + ([f"- {x['action']}: {x['when']}" for x in ctx["same_day"]] or ["- none"])
    lines += ["", "Tight transitions:"] + ([f"- {t}" for t in ctx["tight"]] or ["- none"])
    lines += ["", "Prerequisites:"] + ([f"- {d}" for d in ctx["dependencies"]] or ["- none"])
    lines += ["", "Other issues:"] + ([f"- {i}" for i in ctx["issues"]] or ["- none"])
    return "\n".join(lines)


def gemini_explain(state: WhatIfState) -> WhatIfState:
    try:
        r = structured_call(get_chat_model(), WhatIfExplanation, SYSTEM_PROMPT, _render(state["context"]))
    except AIError as exc:
        return {**rules_explain(state), "error": str(exc)}
    return {"paragraph": r.paragraph.strip(), "risk_level": r.risk_level, "source": "gemini"}


def rules_explain(state: WhatIfState) -> WhatIfState:
    ctx = state["context"]
    conflicts = [f for f in ctx["findings"] if f["type"] == "time_conflict"]
    blockers = [f for f in ctx["findings"] if f["type"] == "dependency_blocker"]
    unknowns = [f for f in ctx["findings"] if f["type"] == "unknown"]
    when = f" on {ctx['range']}" if ctx.get("range") else ""
    parts = [f"You are considering \u201c{ctx['action']}\u201d{when}."]
    if ctx["same_day"]:
        parts.append("That day you already have " + "; ".join(f"{x['action']} ({x['when']})" for x in ctx["same_day"][:5]) + ".")
    else:
        parts.append("No other open commitments are scheduled near that time.")
    if conflicts:
        parts.append(f"Conflict: it overlaps {len(conflicts)} approved commitment{'s' if len(conflicts) != 1 else ''}. " + " ".join(f["explanation"] for f in conflicts))
    if blockers:
        parts.append(" ".join(f["explanation"] for f in blockers))
    if ctx["tight"]:
        parts.append("Watch the transitions: " + "; ".join(ctx["tight"]) + ".")
    elif unknowns:
        parts.append(" ".join(f["explanation"] for f in unknowns))
    parts += ctx["issues"]
    parts.append("Nothing in your ledger changes until you prepare and confirm this change.")
    risk = "conflict" if conflicts else ("caution" if (blockers or unknowns or ctx["tight"] or ctx["issues"]) else "clear")
    return {"paragraph": " ".join(parts), "risk_level": risk, "source": "rules"}


def build_graph():
    g = StateGraph(WhatIfState)
    g.add_node("gather", gather)
    g.add_node("gemini_explain", gemini_explain)
    g.add_node("rules_explain", rules_explain)
    g.add_edge(START, "gather")
    g.add_conditional_edges("gather", route, {"gemini_explain": "gemini_explain", "rules_explain": "rules_explain"})
    g.add_edge("gemini_explain", END)
    g.add_edge("rules_explain", END)
    return g.compile()


GRAPH = build_graph()


def explain_scenario(db, scenario: dict) -> dict:
    s = GRAPH.invoke({"db": db, "scenario": scenario})
    return {"paragraph": s["paragraph"], "risk_level": s["risk_level"], "source": s["source"], "ai_error": s.get("error"),
            "related_commitments": s["context"]["same_day"]}
