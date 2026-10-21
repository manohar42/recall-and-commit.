from app.ai.schemas import ConversationAnalysis, UtteranceDecision
from app.models_commitments import ConversationAIReview
from tests.helpers import conv, payload

CAKE = conv("cake", [("Maya", "Can you pick up the cake Saturday between 4:30 and 5?"), ("Alex", "Yeah, count me in."),
                     ("Maya", "I'll bring the candles."), ("Alex", "Maybe I can help decorate too, not sure.")],
            started="2026-10-17T18:00:00-07:00", title="Cake")


def _analysis(schema, messages):
    assert schema is ConversationAnalysis
    assert "untrusted" in messages[0][1].lower() and "[2] Alex" in messages[1][1]
    return ConversationAnalysis(summary="Maya asked Alex to collect the cake.", has_commitment=True, decisions=[
        UtteranceDecision(utterance_sequence=2, label="commitment", action_text="Pick up the cake for Maya",
                          counterparty="Maya", due_text="Saturday 4:30-5", starts_at="2026-10-24T16:30:00-07:00",
                          ends_at="2026-10-24T17:00:00-07:00", confidence=0.93,
                          explanation="Alex accepted Maya's request.", evidence_quote="count me in"),
        UtteranceDecision(utterance_sequence=3, label="commitment", action_text="Bring candles", confidence=0.9,
                          explanation="Maya's promise, not the user's."),
        UtteranceDecision(utterance_sequence=4, label="uncertain", action_text="Help decorate", confidence=0.4,
                          explanation="Hedged."),
    ])


def test_gemini_reviews_conversation_before_inbox(client, db, fake_gemini):
    model = fake_gemini(_analysis)
    client.post("/api/imports/json", json=payload(CAKE))
    r = client.post("/api/ai/commitments/analyze").json()
    assert r["source"] == "gemini" and r["analyzed"] == 1 and r["candidates_created"] == 1 and r["remaining"] == 0
    assert model.calls == 1
    cands = client.get("/api/commitments/candidates").json()
    assert len(cands) == 1  # other speaker's promise and the hedge are filtered out
    c = cands[0]
    assert c["analysis_source"] == "gemini" and c["ai_label"] == "commitment" and "accepted" in c["ai_explanation"]
    assert c["starts_at"].startswith("2026-10-24T23:30") and c["conversation_title"] == "Cake"
    # second run does nothing: conversation already reviewed
    assert client.post("/api/ai/commitments/analyze").json()["analyzed"] == 0
    # approval keeps the AI-extracted time window and needs no extra input
    item = client.post(f"/api/commitments/candidates/{c['id']}/approve").json()
    assert item["starts_at"].startswith("2026-10-24T23:30") and item["source"]["text"] == "Yeah, count me in."


def test_gemini_failure_is_reported_not_silently_ignored(client, db, fake_gemini):
    def boom(schema, messages):
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
    fake_gemini(boom)
    client.post("/api/imports/json", json=payload(CAKE))
    r = client.post("/api/ai/commitments/analyze").json()
    assert r["failed"] == 1 and r["remaining"] == 1 and "rate limit" in r["errors"][0].lower()
    assert db.query(ConversationAIReview).one().status == "failed"
    assert client.get("/api/commitments/candidates").json() == []


def test_rules_fallback_without_key(client):
    client.post("/api/imports/json", json=payload(CAKE, conv("p", [("Alex", "I will send you the revised proposal by Friday afternoon.")]),
                                                  conv("l", [("Alex", "We should get lunch sometime next week.")])))
    r = client.post("/api/commitments/detect").json()
    assert r["source"] == "rules" and r["analyzed"] == 3
    actions = [c["action_text"] for c in client.get("/api/commitments/candidates").json()]
    assert any("proposal" in a for a in actions) and any("cake" in a.lower() for a in actions)
    assert not any("lunch" in a.lower() or "decorate" in a.lower() for a in actions)


def test_single_conversation_analyze_and_reject(client):
    client.post("/api/imports/json", json=payload(conv("p", [("Alex", "I'll send Priya the test plan tomorrow.")])))
    cid = client.get("/api/conversations").json()[0]["id"]
    assert client.post(f"/api/conversations/{cid}/analyze").json()["candidates_created"] == 1
    detail = client.get(f"/api/conversations/{cid}").json()
    assert detail["analysis_status"] == "completed" and detail["candidate_count"] == 1
    cand = client.get("/api/commitments/candidates").json()[0]
    assert client.post(f"/api/commitments/candidates/{cand['id']}/reject").json()["status"] == "rejected"
    assert client.post(f"/api/commitments/candidates/{cand['id']}/reject").status_code == 409


def test_adding_gemini_key_later_rereviews_rules_results(client, fake_gemini):
    client.post("/api/imports/json", json=payload(CAKE))
    client.post("/api/ai/commitments/analyze")  # rules first (no key)
    assert client.get("/api/commitments/candidates").json()[0]["analysis_source"] == "rules"
    fake_gemini(_analysis)
    assert client.get("/api/ai/commitments/status").json()["remaining"] == 1
    client.post("/api/ai/commitments/analyze")
    cands = client.get("/api/commitments/candidates").json()
    assert [c["analysis_source"] for c in cands] == ["gemini"]
