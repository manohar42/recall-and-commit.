from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CommitmentCandidate(Base):
    __tablename__ = "commitment_candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False, index=True)
    utterance_id: Mapped[int] = mapped_column(ForeignKey("utterances.id"), nullable=False, unique=True)
    utterance_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    ai_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_source: Mapped[str] = mapped_column(String(30), nullable=False, default="rules")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Commitment(Base):
    __tablename__ = "commitments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("commitment_candidates.id"), nullable=True, unique=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    utterance_id: Mapped[int | None] = mapped_column(ForeignKey("utterances.id"), nullable=True)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationAIReview(Base):
    """One row per analyzed conversation: the AI decides before anything reaches the review inbox."""

    __tablename__ = "conversation_ai_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")  # completed | failed
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # gemini | rules
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_commitment: Mapped[bool] = mapped_column(nullable=False, default=False)
    candidates_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
