from datetime import datetime, timezone

from app.models_commitments import Commitment
from app.models_planning import LedgerState


def iso(day,hour): return datetime(2026,10,day,hour,tzinfo=timezone.utc).isoformat()
def test_scenario_conflict_and_confirmation(client,db):
    db.add(LedgerState(id=1,version=0,updated_at=datetime.now(timezone.utc)))
    db.add(Commitment(action_text="Visit Sam",starts_at=datetime(2026,10,17,22,tzinfo=timezone.utc),ends_at=datetime(2026,10,17,23,tzinfo=timezone.utc),status="open"));db.commit()
    created=client.post("/api/scenarios",json={"operation":"add","proposed_change":{"action_text":"Help Maya","starts_at":iso(17,21),"ends_at":iso(18,1),"timezone_name":"America/Phoenix"}})
    assert created.status_code==201
    scenario=client.post(f"/api/scenarios/{created.json()['id']}/evaluate").json()
    assert any(x["type"]=="time_conflict" for x in scenario["findings"])
    prep=client.post(f"/api/scenarios/{scenario['id']}/prepare-change").json()
    before=db.query(Commitment).count(); result=client.post(f"/api/commitment-changes/{prep['id']}/confirm")
    assert result.status_code==200 and db.query(Commitment).count()==before+1
    again=client.post(f"/api/commitment-changes/{prep['id']}/confirm").json();assert again["already_executed"] is True

def test_boundary_is_unknown_not_conflict(client,db):
    db.add(LedgerState(id=1,version=0,updated_at=datetime.now(timezone.utc)));db.add(Commitment(action_text="Visit Sam",starts_at=datetime(2026,10,17,22,tzinfo=timezone.utc),ends_at=datetime(2026,10,17,23,tzinfo=timezone.utc),status="open"));db.commit()
    s=client.post("/api/scenarios",json={"operation":"add","proposed_change":{"action_text":"Help Maya","starts_at":iso(17,21),"ends_at":iso(17,22)}}).json()
    result=client.post(f"/api/scenarios/{s['id']}/evaluate").json()
    assert not any(x["type"]=="time_conflict" for x in result["findings"]);assert any(x["type"]=="unknown" for x in result["findings"])

def test_cancel_does_not_change_ledger(client,db):
    db.add(LedgerState(id=1,version=0,updated_at=datetime.now(timezone.utc)));db.commit()
    s=client.post("/api/scenarios",json={"operation":"add","proposed_change":{"action_text":"Help Maya"}}).json();client.post(f"/api/scenarios/{s['id']}/evaluate");p=client.post(f"/api/scenarios/{s['id']}/prepare-change").json();before=db.query(Commitment).count();assert client.post(f"/api/commitment-changes/{p['id']}/cancel").status_code==200;assert db.query(Commitment).count()==before
