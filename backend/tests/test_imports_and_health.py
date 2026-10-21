import json

from app.config import BACKEND_DIR
from app.services.sample_loader import load_sample_payload, normalize_payload
from tests.helpers import conv, payload

USER_SAMPLE = {"schema_version": "1.0", "source": "sample", "conversations": [
    {"external_id": "sample_laptop_001", "title": "Laptop choice", "started_at": "2026-09-08T18:30:00-07:00",
     "ended_at": "2026-09-08T18:40:00-07:00", "participants": ["Alex", "Maya"], "user_speaker": "Alex",
     "utterances": [{"sequence": 1, "speaker": "Alex", "occurred_at": "2026-09-08T18:30:10-07:00",
                     "text": "The blue laptop is cheaper, but its battery life is not good enough."},
                    {"sequence": 2, "speaker": "Maya", "occurred_at": "2026-09-08T18:31:05-07:00",
                     "text": "The gray model has better battery life and more storage."},
                    {"sequence": 3, "speaker": "Alex", "occurred_at": "2026-09-08T18:32:14-07:00",
                     "text": "Let's choose the gray model, even though it costs a little more."}]},
    {"external_id": "sample_proposal_001", "title": "Proposal review", "started_at": "2026-09-14T14:20:00-07:00",
     "participants": ["Alex", "Priya"], "user_speaker": "Alex",
     "utterances": [{"sequence": 1, "speaker": "Alex", "text": "I will send you the revised proposal by Friday afternoon."}]},
    {"external_id": "sample_weekend_001", "title": "Weekend plans", "started_at": "2026-09-14T15:10:00-07:00",
     "participants": ["Alex", "Sam"], "user_speaker": "Alex",
     "utterances": [{"sequence": 1, "speaker": "Alex", "text": "We should get lunch sometime next week."}]}]}


def test_health_and_ai_status(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/health/ready").json()["status"] == "ready"
    for path in ("/api/ai/status", "/api/ai/config", "/api/health/ai"):
        body = client.get(path).json()
        assert body["configured"] is False and body["mode"] == "rules_fallback"
        assert "key" not in json.dumps(body).lower().replace("google_api_key", "").replace("a key", "")


def test_bundled_sample_file_is_valid_and_month_long():
    p = load_sample_payload()
    assert (BACKEND_DIR / "sample_data" / "conversations.json").exists()
    days = {c.started_at.astimezone().date() for c in p.conversations}
    assert len(p.conversations) >= 60 and len(days) >= 28
    assert all(c.user_speaker == "Alex" for c in p.conversations)


def test_sample_import_endpoint(client):
    r = client.post("/api/imports/sample")
    assert r.status_code == 200, r.text
    assert r.json()["conversations_created"] >= 60
    again = client.post("/api/imports/sample").json()
    assert again["conversations_created"] == 0 and again["conversations_skipped"] >= 60
    assert len(client.get("/api/conversations").json()) >= 60
    assert client.get("/api/imports/sample/info").json()["conversations"] >= 60


def test_user_three_conversation_file_imports(client):
    r = client.post("/api/imports/json", json=USER_SAMPLE)
    assert r.status_code == 200 and r.json()["conversations_created"] == 3


def test_legacy_list_format_imports(client):
    legacy = [{"external": "m-1", "title": "Cake", "day": 4, "hour": 18, "people": ["Alex", "Maya"], "kind": "approved",
               "lines": [["Maya", "Can you pick up the cake Sunday?"], ["Alex", "I will pick up the cake Sunday."]]}]
    assert normalize_payload(legacy)["conversations"][0]["user_speaker"] == "Alex"
    r = client.post("/api/imports/json", json=legacy)
    assert r.status_code == 200 and r.json()["conversations_created"] == 1


def test_large_import_is_not_capped_at_100(client):
    many = payload(*[conv(f"bulk-{i}", [("Alex", f"Note number {i}")]) for i in range(150)])
    r = client.post("/api/imports/json", json=many)
    assert r.status_code == 200 and r.json()["conversations_created"] == 150


def test_invalid_payload_returns_readable_422(client):
    r = client.post("/api/imports/json", json={"conversations": [{"title": "missing fields"}]})
    assert r.status_code == 422 and "detail" in r.json()
