import hashlib
import json

from sqlalchemy.orm import Session

from app.models import Conversation, Utterance
from app.models_commitments import CommitmentCandidate, ConversationAIReview
from app.schemas.imports import ImportSummaryResponse, SampleImportPayload
from app.services.timeutil import as_utc


def content_hash(conv):
    return hashlib.sha256(conv.model_dump_json(exclude={"user_speaker"}).encode()).hexdigest()


def import_sample_payload(db: Session, payload: SampleImportPayload) -> ImportSummaryResponse:
    created = updated = skipped = utterances_created = 0
    for data in payload.conversations:
        digest = content_hash(data)
        existing = db.query(Conversation).filter_by(source_type=payload.source, external_id=data.external_id).first()
        if existing and existing.content_hash == digest:
            if existing.user_speaker != data.user_speaker:
                existing.user_speaker = data.user_speaker
                db.query(ConversationAIReview).filter_by(conversation_id=existing.id).delete()
                updated += 1
            else:
                skipped += 1
            continue
        if existing:
            if db.query(CommitmentCandidate.id).filter_by(conversation_id=existing.id).first():
                skipped += 1  # never rewrite evidence that already backs a commitment candidate
                continue
            db.query(Utterance).filter_by(conversation_id=existing.id).delete()
            db.query(ConversationAIReview).filter_by(conversation_id=existing.id).delete()
            existing.title = data.title
            existing.started_at = as_utc(data.started_at)
            existing.ended_at = as_utc(data.ended_at)
            existing.participants_json = json.dumps(data.participants)
            existing.content_hash = digest
            existing.user_speaker = data.user_speaker
            conv = existing
            updated += 1
        else:
            conv = Conversation(source_type=payload.source, external_id=data.external_id, title=data.title,
                                started_at=as_utc(data.started_at), ended_at=as_utc(data.ended_at),
                                participants_json=json.dumps(data.participants), content_hash=digest,
                                user_speaker=data.user_speaker)
            db.add(conv)
            db.flush()
            created += 1
        for u in data.utterances:
            db.add(Utterance(conversation_id=conv.id, sequence=u.sequence, speaker=u.speaker,
                             occurred_at=as_utc(u.occurred_at), text=u.text))
            utterances_created += 1
    db.commit()
    return ImportSummaryResponse(status="completed", source=payload.source, conversations_received=len(payload.conversations),
                                 conversations_created=created, conversations_updated=updated,
                                 conversations_skipped=skipped, utterances_created=utterances_created)
