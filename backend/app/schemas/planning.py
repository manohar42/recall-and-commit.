from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.commitments import CommitmentOut, aware


class ProposedChange(BaseModel):
    action_text: str | None = Field(default=None, max_length=500)
    counterparty: str | None = Field(default=None, max_length=200)
    due_text: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = None; starts_at: datetime | None = None; ends_at: datetime | None = None
    timezone_name: str | None = Field(default=None, max_length=100)
    status: Literal["open", "done", "cancelled"] | None = None
    @model_validator(mode="after")
    def validate_change(self):
        for name in ("due_at", "starts_at", "ends_at"):
            aware(getattr(self, name))
        if (self.starts_at is None) != (self.ends_at is None): raise ValueError("starts_at and ends_at must be supplied together")
        if self.starts_at and self.ends_at <= self.starts_at: raise ValueError("ends_at must be after starts_at")
        if self.action_text is not None and not self.action_text.strip(): raise ValueError("action_text cannot be blank")
        return self

class ScenarioCreate(BaseModel):
    operation: Literal["add", "update"]
    target_commitment_id: int | None = None
    proposed_change: ProposedChange
    @model_validator(mode="after")
    def target(self):
        if self.operation == "update" and self.target_commitment_id is None: raise ValueError("update requires target_commitment_id")
        if self.operation == "add" and not self.proposed_change.action_text: raise ValueError("add requires action_text")
        return self

class FindingOut(BaseModel):
    id: int; type: Literal["time_conflict", "dependency_blocker", "unknown"]
    affected_record_ids: list[int]; evidence_ids: list[int]; explanation: str; evaluator_version: str

class ScenarioOut(BaseModel):
    id: int; operation: str; target_commitment_id: int | None
    proposed_change: dict[str, Any]; status: str; ledger_version: int
    created_at: datetime; updated_at: datetime; findings: list[FindingOut]
    explanation: str | None = None; explanation_source: str | None = None
    risk_level: str | None = None; related_commitments: list[dict[str, Any]] = []; ai_error: str | None = None

class PreparedChangeOut(BaseModel):
    id: int; scenario_id: int; exact_payload: dict[str, Any]; expected_ledger_version: int
    expires_at: datetime; status: str; idempotency_key: str; result_commitment_id: int | None

class ConfirmationOut(BaseModel):
    status: str; already_executed: bool = False; commitment: CommitmentOut | None = None

class DependencyCreate(BaseModel):
    dependent_id: int
    prerequisite_id: int | None = None
    prerequisite_text: str | None = Field(default=None, max_length=500)
    evidence_ids: list[int] = []
    @model_validator(mode="after")
    def one_prerequisite(self):
        if (self.prerequisite_id is None) == (not self.prerequisite_text):
            raise ValueError("provide exactly one of prerequisite_id or prerequisite_text")
        if self.prerequisite_id == self.dependent_id: raise ValueError("a commitment cannot depend on itself")
        return self

class DependencyOut(BaseModel):
    id: int; dependent_id: int; prerequisite_id: int | None; prerequisite_text: str | None
    evidence_ids: list[int]; review_status: str; created_at: datetime

class RevisionOut(BaseModel):
    id: int; commitment_id: int; previous_values: dict[str, Any]; proposed_values: dict[str, Any]
    evidence_ids: list[int]; review_status: str; created_at: datetime; approved_at: datetime | None

class AssistantMessageRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=1000)
    proposal: ScenarioCreate | None = None
    scenario_id: int | None = None

class AssistantMessageResponse(BaseModel):
    session_id: str; message: str; evidence: list[dict[str, Any]]
    findings: list[FindingOut]; scenario: ScenarioOut | None = None
    pending_action: PreparedChangeOut | None = None; tool_calls: list[str]
    answer_source: str | None = None
