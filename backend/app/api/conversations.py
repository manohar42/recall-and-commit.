import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models import Conversation
from app.models_commitments import CommitmentCandidate, ConversationAIReview
from app.schemas.commitments import ConversationAnalysisOut
from app.schemas.imports import ConversationDetail, ConversationListItem, UserSpeakerUpdate
from app.services.commitments import ReviewError, analyze_conversation
from app.storage import get_db

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


def summary(c, review=None, candidates=0):
    return {"id": c.id, "external_id": c.external_id, "source_type": c.source_type, "title": c.title,
            "started_at": c.started_at, "participants": json.loads(c.participants_json), "user_speaker": c.user_speaker,
            "utterance_count": len(c.utterances), "analysis_status": review.status if review else None,
            "analysis_source": review.source if review else None, "analysis_summary": review.summary if review else None,
            "candidate_count": candidates}


def _load(db, conversation_id):
    c = db.query(Conversation).options(selectinload(Conversation.utterances)).filter_by(id=conversation_id).first()
    if not c:
        raise HTTPException(404, "Conversation not found")
    return c


@router.get("", response_model=list[ConversationListItem])
def list_all(db: Session = Depends(get_db)):
    reviews = {r.conversation_id: r for r in db.query(ConversationAIReview).all()}
    counts = dict(db.query(CommitmentCandidate.conversation_id, func.count()).group_by(CommitmentCandidate.conversation_id).all())
    rows = db.query(Conversation).options(selectinload(Conversation.utterances)).order_by(Conversation.started_at.desc())
    return [summary(c, reviews.get(c.id), counts.get(c.id, 0)) for c in rows]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_one(conversation_id: int, db: Session = Depends(get_db)):
    c = _load(db, conversation_id)
    review = db.query(ConversationAIReview).filter_by(conversation_id=c.id).first()
    count = db.query(CommitmentCandidate).filter_by(conversation_id=c.id).count()
    return {**summary(c, review, count), "ended_at": c.ended_at,
            "utterances": [{"id": u.id, "sequence": u.sequence, "speaker": u.speaker, "occurred_at": u.occurred_at, "text": u.text}
                           for u in sorted(c.utterances, key=lambda x: x.sequence)]}


@router.post("/{conversation_id}/analyze", response_model=ConversationAnalysisOut)
def analyze_one(conversation_id: int, db: Session = Depends(get_db)):
    try:
        return analyze_conversation(db, _load(db, conversation_id))
    except ReviewError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.patch("/{conversation_id}/user-speaker")
def set_speaker(conversation_id: int, body: UserSpeakerUpdate, db: Session = Depends(get_db)):
    c = _load(db, conversation_id)
    if body.user_speaker not in {u.speaker for u in c.utterances}:
        raise HTTPException(422, "user_speaker must match an utterance speaker")
    if c.user_speaker != body.user_speaker:
        c.user_speaker = body.user_speaker
        db.query(ConversationAIReview).filter_by(conversation_id=c.id).delete()  # re-review with the new identity
    db.commit()
    return {"conversation_id": c.id, "user_speaker": c.user_speaker}
