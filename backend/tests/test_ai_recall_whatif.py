from datetime import datetime, timezone

from app.ai.schemas import RecallAnswer, WhatIfExplanation
from app.models_commitments import Commitment
from app.models_planning import LedgerState
from tests.test_imports_and_health import USER_SAMPLE


def test_recall_paragraph_without_key(client):
    client.post("/api/imports/json", json=USER_SAMPLE)
    r = client.post("/api/recall", json={"question": "Which laptop did we choose?"}).json()
    assert r["answer_source"] == "rules" and not r["insufficient_evidence"]
    assert "gray" in r["answer"].lower() and r["citations"] and r["results"][0]["conversation_title"] == "Laptop choice"
    first = r["results"][0]
    detail = client.get(f"/api/conversations/{first['conversation_id']}").json()  # "View conversation"
    assert len(detail["utterances"]) == 3


def test_recall_with_gemini_paragraph_and_citation_validation(client, fake_gemini):
    def answer(schema, messages):
        assert schema is RecallAnswer and "[1]" in messages[1][1]
        return RecallAnswer(answer="You and Maya chose the gray laptop because of its battery life and storage [1]. [9]",
                            citations=[1, 9])
    fake_gemini(answer)
    client.post("/api/imports/json", json=USER_SAMPLE)
    r = client.post("/api/recall", json={"question": "laptop battery"}).json()
    assert r["answer_source"] == "gemini" and r["citations"] == [1]


def test_recall_no_evidence(client):
    r = client.post("/api/recall", json={"question": "zebra xylophone"}).json()
    assert r["insufficient_evidence"] and r["results"] == []


def _ledger(db):
    db.add(LedgerState(id=1, version=0, updated_at=datetime.now(timezone.utc)))
    db.add(Commitment(action_text="Pick up the cake", starts_at=datetime(2026, 10, 24, 23, 30, tzinfo=timezone.utc),
                      ends_at=datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc), status="open"))
    db.add(Commitment(action_text="Birthday dinner", starts_at=datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc),
                      ends_at=datetime(2026, 10, 25, 3, 30, tzinfo=timezone.utc), status="open"))
    db.commit()


WHATIF = {"operation": "add", "proposed_change": {"action_text": "Decorate Lucia's with Maya",
          "starts_at": "2026-10-24T23:45:00+00:00", "ends_at": "2026-10-25T01:15:00+00:00", "timezone_name": "America/Phoenix"}}


def test_whatif_paragraph_without_key(client, db):
    _ledger(db)
    s = client.post("/api/scenarios", json=WHATIF).json()
    r = client.post(f"/api/scenarios/{s['id']}/evaluate").json()
    assert any(f["type"] == "time_conflict" for f in r["findings"])
    assert r["risk_level"] == "conflict" and r["explanation_source"] == "rules"
    assert "Pick up the cake" in r["explanation"] and "15 minutes" in r["explanation"]
    assert len(r["related_commitments"]) == 2
    assert db.query(Commitment).count() == 2  # evaluation never writes to the ledger


def test_whatif_with_gemini(client, db, fake_gemini):
    def explain(schema, messages):
        assert schema is WhatIfExplanation and "time_conflict" in messages[1][1]
        return WhatIfExplanation(paragraph="Decorating overlaps the cake pickup.", risk_level="conflict")
    fake_gemini(explain)
    _ledger(db)
    s = client.post("/api/scenarios", json=WHATIF).json()
    r = client.post(f"/api/scenarios/{s['id']}/evaluate").json()
    assert r["explanation_source"] == "gemini" and r["explanation"] == "Decorating overlaps the cake pickup."
    assert client.get(f"/api/scenarios/{s['id']}").json()["explanation"] == r["explanation"]


def test_assistant_uses_recall_and_ledger(client, db):
    client.post("/api/imports/json", json=USER_SAMPLE)
    _ledger(db)
    r = client.post("/api/assistant/messages", json={"message": "What did we decide about the laptop?"}).json()
    assert "recall_answer" in r["tool_calls"] and "gray" in r["message"].lower()
    r = client.post("/api/assistant/messages", json={"message": "What did I agree to for Saturday?"}).json()
    assert "list_commitments" in r["tool_calls"] and "2 approved" in r["message"]
