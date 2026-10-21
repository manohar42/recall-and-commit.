from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LedgerState(Base):
    __tablename__ = "ledger_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PlanningScenario(Base):
    __tablename__ = "planning_scenarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    target_commitment_id: Mapped[int | None] = mapped_column(ForeignKey("commitments.id"), nullable=True)
    proposed_change_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    ledger_version: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ScenarioFinding(Base):
    __tablename__ = "scenario_findings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("planning_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_type: Mapped[str] = mapped_column(String(40), nullable=False)
    affected_record_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    evidence_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(30), nullable=False, default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CommitmentRevision(Base):
    __tablename__ = "commitment_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commitment_id: Mapped[int] = mapped_column(ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_values_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CommitmentDependency(Base):
    __tablename__ = "commitment_dependencies"
    __table_args__ = (UniqueConstraint("dependent_id", "prerequisite_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dependent_id: Mapped[int] = mapped_column(ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    prerequisite_id: Mapped[int | None] = mapped_column(ForeignKey("commitments.id", ondelete="CASCADE"), nullable=True)
    prerequisite_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class PreparedChange(Base):
    __tablename__ = "prepared_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("planning_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    exact_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    expected_ledger_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_commitment_id: Mapped[int | None] = mapped_column(ForeignKey("commitments.id"), nullable=True)


class AssistantSession(Base):
    __tablename__ = "assistant_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    active_scenario_id: Mapped[int | None] = mapped_column(ForeignKey("planning_scenarios.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
