from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class SampleUtteranceInput(BaseModel):
    sequence: int = Field(gt=0)
    speaker: str = Field(min_length=1, max_length=100)
    occurred_at: datetime | None = None
    text: str = Field(min_length=1, max_length=10000)
    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value: raise ValueError("utterance text cannot be empty")
        return value

class SampleConversationInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=255)
    started_at: datetime
    ended_at: datetime | None = None
    participants: list[str] = Field(min_length=1)
    user_speaker: str | None = None
    utterances: list[SampleUtteranceInput] = Field(min_length=1, max_length=1000)
    @field_validator("utterances")
    @classmethod
    def unique_sequences(cls, values):
        seq = [u.sequence for u in values]
        if len(seq) != len(set(seq)): raise ValueError("utterance sequence numbers must be unique")
        return values
    @model_validator(mode="after")
    def validate_conversation(self):
        if self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be before started_at")
        speakers = {u.speaker for u in self.utterances}
        if self.user_speaker and self.user_speaker not in speakers:
            raise ValueError("user_speaker must match an utterance speaker")
        return self

class SampleImportPayload(BaseModel):
    schema_version: str
    source: str = Field(min_length=1, max_length=50)
    conversations: list[SampleConversationInput] = Field(min_length=1, max_length=5000)

class ImportSummaryResponse(BaseModel):
    status: str
    source: str
    conversations_received: int
    conversations_created: int
    conversations_updated: int
    conversations_skipped: int
    utterances_created: int

class UtteranceResponse(BaseModel):
    id: int
    sequence: int
    speaker: str
    occurred_at: datetime | None
    text: str

class ConversationListItem(BaseModel):
    id: int
    analysis_status: str | None = None
    analysis_source: str | None = None
    analysis_summary: str | None = None
    candidate_count: int = 0
    external_id: str
    source_type: str
    title: str
    started_at: datetime
    participants: list[str]
    user_speaker: str | None
    utterance_count: int

class ConversationDetail(ConversationListItem):
    ended_at: datetime | None
    utterances: list[UtteranceResponse]

class UserSpeakerUpdate(BaseModel):
    user_speaker: str = Field(min_length=1, max_length=100)
