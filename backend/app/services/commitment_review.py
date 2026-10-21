import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Conversation, Utterance
from app.models_commitments import Commitment
from app.models_planning import CommitmentRevision
from app.services.ledger import bump_ledger_version
from app.services.timeutil import as_utc, utc_now

VALID_DUE = {"overdue", "soon", "undated", "later"}
MAX_DT = datetime.max.replace(tzinfo=timezone.utc)

def due_group(item: Commitment, now: datetime, soon_days: int) -> str:
    if item.status in {"done", "cancelled"}: return item.status
    if item.due_at is None: return "undated"
    due = as_utc(item.due_at)
    if due < now: return "overdue"
    if due <= now + timedelta(days=soon_days): return "soon"
    return "later"

def commitment_values(item: Commitment) -> dict:
    return {k: (as_utc(v).isoformat() if isinstance(v, datetime) else v) for k, v in {
        "action_text": item.action_text, "counterparty": item.counterparty, "due_text": item.due_text,
        "due_at": item.due_at, "starts_at": item.starts_at, "ends_at": item.ends_at,
        "timezone_name": item.timezone_name, "status": item.status,
    }.items()}

def serialize_commitment(db: Session, item: Commitment, now: datetime | None = None, soon_days: int = 7) -> dict:
    now = now or utc_now(); source = None
    if item.utterance_id and item.conversation_id:
        utterance = db.get(Utterance, item.utterance_id); conversation = db.get(Conversation, item.conversation_id)
        if utterance and conversation and utterance.conversation_id == conversation.id:
            source = {"conversation_id": conversation.id, "conversation_title": conversation.title,
                      "utterance_id": utterance.id, "sequence": utterance.sequence,
                      "speaker": utterance.speaker, "text": utterance.text}
    return {"id": item.id, "candidate_id": item.candidate_id, "conversation_id": item.conversation_id,
            "utterance_id": item.utterance_id, "action_text": item.action_text,
            "counterparty": item.counterparty, "due_text": item.due_text,
            "due_at": as_utc(item.due_at), "starts_at": as_utc(item.starts_at), "ends_at": as_utc(item.ends_at),
            "timezone_name": item.timezone_name, "status": item.status, "version": item.version,
            "completed_at": as_utc(item.completed_at), "source": source,
            "due_group": due_group(item, now, soon_days)}

def list_commitments(db: Session, status=None, due=None, limit=100) -> list[dict]:
    if due and due not in VALID_DUE: raise ValueError("invalid due filter")
    q = db.query(Commitment)
    if status: q = q.filter(Commitment.status == status)
    now = utc_now(); rows = [serialize_commitment(db, item, now) for item in q.all()]
    if due: rows = [r for r in rows if r["due_group"] == due]
    rows.sort(key=lambda r: (r["due_at"] is None, r["due_at"] or MAX_DT, r["id"]))
    return rows[:limit]

def get_review_summary(db: Session, soon_days=7, completed_days=7) -> dict:
    now=utc_now(); rows=[serialize_commitment(db,i,now,soon_days) for i in db.query(Commitment).all()]
    cutoff=now-timedelta(days=completed_days)
    return {"overdue":[r for r in rows if r["due_group"]=="overdue"],
            "due_soon":[r for r in rows if r["due_group"]=="soon"],
            "undated":[r for r in rows if r["due_group"]=="undated"],
            "recently_completed":[r for r in rows if r["status"]=="done" and r["completed_at"] and r["completed_at"]>=cutoff]}

def validate_changes(item: Commitment, changes: dict) -> dict:
    allowed={"action_text","counterparty","due_text","due_at","starts_at","ends_at","timezone_name","status"}
    changes={k:v for k,v in changes.items() if k in allowed}
    if "action_text" in changes:
        value=(changes["action_text"] or "").strip()
        if not value: raise ValueError("action_text cannot be blank or null")
        changes["action_text"]=value
    if "status" in changes and changes["status"] is None: raise ValueError("status cannot be null")
    start=changes.get("starts_at",item.starts_at); end=changes.get("ends_at",item.ends_at)
    if (start is None)!=(end is None): raise ValueError("starts_at and ends_at must be supplied or cleared together")
    if start and as_utc(end)<=as_utc(start): raise ValueError("ends_at must be after starts_at")
    for key in ("due_at","starts_at","ends_at"):
        if key in changes: changes[key]=as_utc(changes[key])
    return changes

def patch_commitment(db: Session, commitment_id: int, changes: dict) -> dict | None:
    item=db.get(Commitment,commitment_id)
    if item is None: return None
    changes=validate_changes(item,changes); before=commitment_values(item); old=item.status
    for key,value in changes.items(): setattr(item,key,value)
    if old!="done" and item.status=="done": item.completed_at=utc_now()
    elif old=="done" and item.status!="done": item.completed_at=None
    item.version+=1
    db.add(CommitmentRevision(commitment_id=item.id, previous_values_json=json.dumps(before),
        proposed_values_json=json.dumps(commitment_values(item)), evidence_ids_json=json.dumps([item.utterance_id] if item.utterance_id else []),
        review_status="approved", approved_at=utc_now()))
    bump_ledger_version(db)
    try: db.commit(); db.refresh(item)
    except Exception: db.rollback(); raise
    return serialize_commitment(db,item)
