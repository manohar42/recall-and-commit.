"""Structured outputs Gemini must return. LangChain enforces them with JSON-schema structured output."""
from typing import Literal

from pydantic import BaseModel, Field


class UtteranceDecision(BaseModel):
    utterance_sequence: int = Field(description="Sequence number of the user's line being judged.")
    label: Literal["commitment", "not_commitment", "uncertain"] = Field(
        description="commitment = the user clearly promised or accepted a future action."
    )
    action_text: str | None = Field(default=None, description="Short imperative task, e.g. 'Send Priya the revised proposal'.")
    counterparty: str | None = Field(default=None, description="Person the promise was made to, if any.")
    due_text: str | None = Field(default=None, description="Deadline wording as spoken, e.g. 'Friday afternoon'.")
    due_at: str | None = Field(
        default=None,
        description="ISO-8601 datetime with UTC offset, resolved relative to when the line was said. Null if unclear.",
    )
    starts_at: str | None = Field(default=None, description="ISO-8601 start if a time window was stated, else null.")
    ends_at: str | None = Field(default=None, description="ISO-8601 end if a time window was stated, else null.")
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(description="One sentence grounded in the transcript.")
    evidence_quote: str | None = Field(default=None, description="Exact words from the user's line.")


class ConversationAnalysis(BaseModel):
    summary: str = Field(description="One or two sentences on what the conversation was about.")
    has_commitment: bool
    decisions: list[UtteranceDecision] = Field(default_factory=list)


class RecallAnswer(BaseModel):
    answer: str = Field(description="One paragraph (3-6 sentences) answering the question with [n] citations.")
    citations: list[int] = Field(default_factory=list, description="Evidence numbers actually used.")
    insufficient_evidence: bool = False


class WhatIfExplanation(BaseModel):
    paragraph: str = Field(description="One paragraph explaining the tasks involved, conflicts, and other issues.")
    risk_level: Literal["clear", "caution", "conflict"]
