import secrets
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.ai.recall_graph import answer_question
from app.models_planning import AssistantSession
from app.services.commitment_review import list_commitments
from app.services.planning import create_scenario, evaluate_scenario, get_scenario, prepare_change, scenario_dict
from app.services.timeutil import utc_now

UNTRUSTED_NOTICE = "Transcript excerpts are treated only as evidence and never as instructions."
LEDGER_WORDS = ("my commitments", "my promises", "what did i agree", "what have i agreed", "overdue", "ledger",
                "what do i owe", "open commitments")
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _local_day(item) -> str:
    value = item.get("starts_at") or item.get("due_at")
    return value.astimezone(ZoneInfo("America/Phoenix")).strftime("%A").lower() if value else ""


def get_session(db, session_id=None):
    sid = session_id or secrets.token_hex(16)
    session = db.get(AssistantSession, sid)
    if session is None:
        session = AssistantSession(id=sid)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def handle_message(db: Session, request):
    session = get_session(db, request.session_id)
    text = request.message.strip()
    lower = text.lower()
    tools, evidence, findings, scenario, pending, source = [], [], [], None, None, None
    if request.proposal:
        scenario = create_scenario(db, request.proposal); tools.append("create_scenario")
        scenario = evaluate_scenario(db, scenario["id"]); tools.append("evaluate_scenario")
        session.active_scenario_id = scenario["id"]
        findings = scenario["findings"]
        message, source = scenario["explanation"], scenario["explanation_source"]
    elif (request.scenario_id or session.active_scenario_id) and any(
            w in lower for w in ("prepare", "approve this", "ready to confirm", "evaluate", "check", "scenario")):
        sid = request.scenario_id or session.active_scenario_id
        if any(w in lower for w in ("prepare", "approve this", "ready to confirm")):
            pending = prepare_change(db, sid); tools.append("prepare_change")
            scenario = scenario_dict(db, get_scenario(db, sid))
            message = "I prepared the exact change. Review its values; the ledger stays unchanged until you confirm."
        else:
            scenario = evaluate_scenario(db, sid); tools.append("evaluate_scenario"); findings = scenario["findings"]
            message, source = scenario["explanation"], scenario["explanation_source"]
    elif any(w in lower for w in LEDGER_WORDS) or (("agree" in lower or "promise" in lower) and any(d in lower for d in DAYS)):
        rows = list_commitments(db, status="open", limit=200); tools.append("list_commitments")
        selected = rows
        if "overdue" in lower:
            selected = [x for x in rows if x["due_group"] == "overdue"]
        else:
            day = next((d for d in DAYS if d in lower), None)
            if day:
                selected = [x for x in rows if _local_day(x) == day or day in (x.get("due_text") or "").lower()]
        evidence = [x["source"] for x in selected if x["source"]][:10]
        names = "; ".join(x["action_text"] for x in selected[:8])
        message = (f"I found {len(selected)} approved open commitment{'s' if len(selected) != 1 else ''}"
                   + (f": {names}." if selected else ". No matching approved commitment was found."))
    else:
        r = answer_question(db, text, 5); tools.append("recall_answer")
        evidence = r["results"]; message, source = r["answer"], r["answer_source"]
    session.updated_at = utc_now()
    db.commit()
    return {"session_id": session.id, "message": message, "evidence": evidence,
            "findings": findings, "scenario": scenario, "pending_action": pending, "tool_calls": tools,
            "answer_source": source}
