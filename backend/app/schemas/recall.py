from datetime import datetime

from pydantic import BaseModel, Field


class RecallRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=6, ge=1, le=20)


class RecallEvidence(BaseModel):
    index: int
    conversation_id: int
    conversation_title: str
    started_at: datetime | None = None
    sequence_start: int
    sequence_end: int
    excerpt: str
    score: float


class RecallResponse(BaseModel):
    question: str
    answer: str
    answer_source: str
    citations: list[int]
    insufficient_evidence: bool
    ai_error: str | None = None
    results: list[RecallEvidence]
