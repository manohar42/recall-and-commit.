from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Status = Literal["open", "done", "cancelled"]
DueGroup = Literal["overdue", "soon", "undated", "later", "done", "cancelled"]

def aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must include a UTC offset")
    return value

class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; conversation_id: int; utterance_id: int; utterance_sequence: int
    speaker: str | None; source_text: str; action_text: str
    counterparty: str | None; due_text: str | None; due_at: datetime | None
    starts_at: datetime | None = None; ends_at: datetime | None = None
    confidence: float; status: str
    ai_label: str | None = None; ai_explanation: str | None = None; analysis_source: str = "rules"
    conversation_title: str | None = None

class ApproveRequest(BaseModel):
    action_text: str | None = Field(default=None, min_length=1, max_length=500)
    counterparty: str | None = Field(default=None, max_length=200)
    due_text: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone_name: str | None = Field(default=None, max_length=100)
    _dates = field_validator("due_at", "starts_at", "ends_at")(classmethod(lambda cls, v: aware(v)))
    @model_validator(mode="after")
    def interval(self):
        if (self.starts_at is None) != (self.ends_at is None): raise ValueError("starts_at and ends_at must be supplied together")
        if self.starts_at and self.ends_at <= self.starts_at: raise ValueError("ends_at must be after starts_at")
        return self

class SourceOut(BaseModel):
    conversation_id: int; conversation_title: str; utterance_id: int
    sequence: int; speaker: str | None; text: str

class CommitmentOut(BaseModel):
    id: int; candidate_id: int | None; conversation_id: int | None; utterance_id: int | None
    action_text: str; counterparty: str | None; due_text: str | None; due_at: datetime | None
    starts_at: datetime | None; ends_at: datetime | None; timezone_name: str | None
    status: Status; version: int; completed_at: datetime | None
    source: SourceOut | None; due_group: DueGroup

class AnalyzeSummary(BaseModel):
    source: str; analyzed: int; failed: int; candidates_created: int; remaining: int
    total_conversations: int; conversations_without_user_speaker: int; errors: list[str]

class AnalysisStatus(BaseModel):
    total_conversations: int; analyzed: int; failed: int; remaining: int; source: str

class ConversationAnalysisOut(BaseModel):
    conversation_id: int; status: str; source: str; error: str | None
    candidates_created: int; summary: str | None

class CommitmentPatch(BaseModel):
    action_text: str | None = Field(default=None, max_length=500)
    counterparty: str | None = Field(default=None, max_length=200)
    due_text: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = None; starts_at: datetime | None = None; ends_at: datetime | None = None
    timezone_name: str | None = Field(default=None, max_length=100); status: Status | None = None
    _dates = field_validator("due_at", "starts_at", "ends_at")(classmethod(lambda cls, v: aware(v)))

class ReviewSummary(BaseModel):
    overdue: list[CommitmentOut]; due_soon: list[CommitmentOut]
    undated: list[CommitmentOut]; recently_completed: list[CommitmentOut]

class EvidenceIssue(BaseModel):
    record_type: str; record_id: int; code: str; detail: str
