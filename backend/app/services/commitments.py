"""Commitment review pipeline. AI (Gemini via LangGraph) judges each conversation before candidates exist."""
import json

from sqlalchemy.orm import Session, selectinload

from app.ai.commitment_graph import review_conversation
from app.config import get_settings
from app.models import Conversation
from app.models_commitments import Commitment, CommitmentCandidate, ConversationAIReview
from app.services.ledger import bump_ledger_version
from app.services.timeutil import as_utc, utc_now


class ReviewError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def conversation_payload(conv: Conversation) -> dict:
    return {
        "id": conv.id, "title": conv.title, "user_speaker": conv.user_speaker,
        "started_at": as_utc(conv.started_at).isoformat(), "started_at_dt": as_utc(conv.started_at),
        "participants": json.loads(conv.participants_json or "[]"),
        "utterances": [{"id": u.id, "sequence": u.sequence, "speaker": u.speaker, "text": u.text,
                        "occurred_at": as_utc(u.occurred_at).isoformat() if u.occurred_at else None}
                       for u in sorted(conv.utterances, key=lambda x: x.sequence)],
    }


def _needs_review(conv: Conversation, review: ConversationAIReview | None, source: str) -> bool:
    if not conv.user_speaker:
        return False
    if review is None or review.status != "completed" or review.content_hash != conv.content_hash:
        return True
    # A rules-fallback review is redone once Gemini becomes available.
    return review.source == "rules" and source == "gemini"


def analyze_conversation(db: Session, conv: Conversation) -> dict:
    """Run the commitment graph for one conversation and store pending candidates for human review."""
    if not conv.user_speaker:
        raise ReviewError("Set the user's speaker for this conversation before analysis", 422)
    state = review_conversation(conversation_payload(conv))
    review = db.query(ConversationAIReview).filter_by(conversation_id=conv.id).first()
    if review is None:
        review = ConversationAIReview(conversation_id=conv.id, source=state["source"], content_hash=conv.content_hash)
        db.add(review)
    review.source, review.model, review.content_hash = state["source"], state.get("model"), conv.content_hash
    review.analyzed_at = utc_now()
    if state.get("error"):
        review.status, review.error, review.candidates_created = "failed", state["error"], 0
        db.commit()
        return {"conversation_id": conv.id, "status": "failed", "source": state["source"], "error": state["error"],
                "candidates_created": 0, "summary": None}
    if state["source"] == "gemini":
        # Gemini supersedes earlier rules-fallback suggestions that the user has not acted on yet.
        db.query(CommitmentCandidate).filter_by(conversation_id=conv.id, status="pending", analysis_source="rules").delete()
    existing = {x[0] for x in db.query(CommitmentCandidate.utterance_id).filter_by(conversation_id=conv.id)}
    created = 0
    for c in state["candidates"]:
        u = c["utterance"]
        if u["id"] in existing:
            continue
        db.add(CommitmentCandidate(
            conversation_id=conv.id, utterance_id=u["id"], utterance_sequence=u["sequence"], speaker=u["speaker"],
            source_text=u["text"], action_text=c["action_text"], counterparty=c["counterparty"], due_text=c["due_text"],
            due_at=c["due_at"], starts_at=c["starts_at"], ends_at=c["ends_at"], confidence=c["confidence"],
            status="pending", ai_label=c["ai_label"], ai_explanation=c["ai_explanation"], analysis_source=state["source"]))
        existing.add(u["id"])
        created += 1
    review.status, review.error = "completed", None
    review.summary = state["analysis"].summary
    review.has_commitment = bool(state["candidates"])
    review.candidates_created = created
    db.commit()
    return {"conversation_id": conv.id, "status": "completed", "source": state["source"], "error": None,
            "candidates_created": created, "summary": review.summary}


def analyze_pending(db: Session, limit: int | None = None) -> dict:
    source = "gemini" if get_settings().ai_configured else "rules"
    limit = limit or get_settings().analyze_batch_size
    reviews = {r.conversation_id: r for r in db.query(ConversationAIReview).all()}
    conversations = db.query(Conversation).options(selectinload(Conversation.utterances)).order_by(Conversation.started_at).all()
    todo = [c for c in conversations if _needs_review(c, reviews.get(c.id), source)]
    batch, results = todo[:limit], []
    for conv in batch:
        results.append(analyze_conversation(db, conv))
        if results[-1]["status"] == "failed" and "rate limit" in (results[-1]["error"] or "").lower():
            break  # stop early on quota errors instead of failing every remaining conversation
    failed = [r for r in results if r["status"] == "failed"]
    processed = len(results)
    return {
        "source": source, "analyzed": processed - len(failed), "failed": len(failed),
        "candidates_created": sum(r["candidates_created"] for r in results),
        "remaining": len(todo) - (processed - len(failed)),
        "total_conversations": len(conversations),
        "conversations_without_user_speaker": sum(1 for c in conversations if not c.user_speaker),
        "errors": sorted({r["error"] for r in failed if r["error"]}),
    }


def analysis_status(db: Session) -> dict:
    source = "gemini" if get_settings().ai_configured else "rules"
    reviews = {r.conversation_id: r for r in db.query(ConversationAIReview).all()}
    conversations = db.query(Conversation).all()
    pending = sum(1 for c in conversations if _needs_review(c, reviews.get(c.id), source))
    return {"total_conversations": len(conversations), "analyzed": sum(1 for r in reviews.values() if r.status == "completed"),
            "failed": sum(1 for r in reviews.values() if r.status == "failed"), "remaining": pending, "source": source}


def _pending(db, candidate_id):
    item = db.get(CommitmentCandidate, candidate_id)
    if not item:
        raise ReviewError("Candidate not found", 404)
    if item.status != "pending":
        raise ReviewError(f"Candidate already {item.status}", 409)
    return item


def approve_candidate(db, candidate_id, edits):
    cand = _pending(db, candidate_id)
    conv = db.get(Conversation, cand.conversation_id)
    if not conv or conv.user_speaker != cand.speaker:
        raise ReviewError("This candidate is no longer attributed to the conversation's user speaker", 409)
    for field in ("action_text", "counterparty", "due_text", "due_at", "starts_at", "ends_at"):
        if field in edits and edits[field] is not None:
            setattr(cand, field, as_utc(edits[field]) if field in ("due_at", "starts_at", "ends_at") else edits[field])
    starts, ends = as_utc(cand.starts_at), as_utc(cand.ends_at)
    if not (starts and ends and ends > starts):
        starts = ends = None
    cand.status = "approved"
    cand.reviewed_at = utc_now()
    item = Commitment(candidate_id=cand.id, conversation_id=cand.conversation_id, utterance_id=cand.utterance_id,
                      action_text=cand.action_text, counterparty=cand.counterparty, due_text=cand.due_text,
                      due_at=as_utc(cand.due_at) or ends, starts_at=starts, ends_at=ends,
                      timezone_name=edits.get("timezone_name") or "America/Phoenix", status="open")
    db.add(item)
    bump_ledger_version(db)
    try:
        db.commit()
        db.refresh(item)
    except Exception:
        db.rollback()
        raise
    return item


def reject_candidate(db, candidate_id):
    cand = _pending(db, candidate_id)
    cand.status = "rejected"
    cand.reviewed_at = utc_now()
    db.commit()
    db.refresh(cand)
    return cand


def list_misattributed_candidates(db):
    rows = (db.query(CommitmentCandidate, Conversation)
            .join(Conversation, Conversation.id == CommitmentCandidate.conversation_id)
            .filter(CommitmentCandidate.status == "pending").all())
    return [c for c, conv in rows if not conv.user_speaker or c.speaker != conv.user_speaker]
