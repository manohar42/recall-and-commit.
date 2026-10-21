import json
import secrets
from datetime import timedelta

from app.models_commitments import Commitment
from app.models_planning import (
    CommitmentDependency,
    CommitmentRevision,
    PlanningScenario,
    PreparedChange,
    ScenarioFinding,
)
from app.services.commitment_review import (
    commitment_values,
    serialize_commitment,
    validate_changes,
)
from app.services.ledger import bump_ledger_version, get_ledger_version
from app.services.timeutil import as_utc, utc_now

EVALUATOR_VERSION="1.0"
class PlanningError(Exception):
    def __init__(self,message,status_code=422): super().__init__(message); self.status_code=status_code

def dumps(value):
    return json.dumps(value,default=lambda x: as_utc(x).isoformat() if hasattr(x,"isoformat") else str(x))
def loads(value): return json.loads(value)
def scenario_dict(db,item):
    findings=[{"id":f.id,"type":f.finding_type,"affected_record_ids":loads(f.affected_record_ids_json),
        "evidence_ids":loads(f.evidence_ids_json),"explanation":f.explanation,"evaluator_version":f.evaluator_version}
        for f in db.query(ScenarioFinding).filter_by(scenario_id=item.id).order_by(ScenarioFinding.id)]
    return {"id":item.id,"operation":item.operation,"target_commitment_id":item.target_commitment_id,
        "proposed_change":loads(item.proposed_change_json),"status":item.status,"ledger_version":item.ledger_version,
        "created_at":as_utc(item.created_at),"updated_at":as_utc(item.updated_at),"findings":findings,
        "explanation":item.explanation,"explanation_source":item.explanation_source}
def prepared_dict(item):
    return {"id":item.id,"scenario_id":item.scenario_id,"exact_payload":loads(item.exact_payload_json),
        "expected_ledger_version":item.expected_ledger_version,"expires_at":as_utc(item.expires_at),"status":item.status,
        "idempotency_key":item.idempotency_key,"result_commitment_id":item.result_commitment_id}
def create_scenario(db,payload):
    if payload.operation=="update" and not db.get(Commitment,payload.target_commitment_id): raise PlanningError("Target commitment not found",404)
    item=PlanningScenario(operation=payload.operation,target_commitment_id=payload.target_commitment_id,
        proposed_change_json=dumps(payload.proposed_change.model_dump(mode="json",exclude_none=False)),status="draft",
        ledger_version=get_ledger_version(db),updated_at=utc_now())
    db.add(item); db.commit(); db.refresh(item); return scenario_dict(db,item)
def get_scenario(db,scenario_id):
    item=db.get(PlanningScenario,scenario_id)
    if not item: raise PlanningError("Scenario not found",404)
    return item
def add_finding(db,scenario_id,kind,ids,evidence,explanation):
    db.add(ScenarioFinding(scenario_id=scenario_id,finding_type=kind,affected_record_ids_json=dumps(ids),
        evidence_ids_json=dumps(evidence),explanation=explanation,evaluator_version=EVALUATOR_VERSION))
def evaluate_scenario(db,scenario_id):
    scenario=get_scenario(db,scenario_id); change=loads(scenario.proposed_change_json)
    db.query(ScenarioFinding).filter_by(scenario_id=scenario.id).delete()
    start=datetime_value(change.get("starts_at")); end=datetime_value(change.get("ends_at"))
    if start and end:
        for item in db.query(Commitment).filter(Commitment.status=="open").all():
            if scenario.target_commitment_id==item.id or not item.starts_at or not item.ends_at: continue
            a,b=as_utc(item.starts_at),as_utc(item.ends_at)
            if start < b and a < end:
                add_finding(db,scenario.id,"time_conflict",[item.id],[item.utterance_id] if item.utterance_id else [],f"Proposed time overlaps '{item.action_text}'.")
            elif end==a or start==b:
                add_finding(db,scenario.id,"unknown",[item.id],[item.utterance_id] if item.utterance_id else [],f"No interval overlap with '{item.action_text}', but transition or travel time is unknown.")
    else:
        add_finding(db,scenario.id,"unknown",[],[],"The proposal has no complete start/end interval, so occupancy conflicts cannot be evaluated.")
    if scenario.target_commitment_id:
        for dep in db.query(CommitmentDependency).filter_by(dependent_id=scenario.target_commitment_id,review_status="approved"):
            if dep.prerequisite_id:
                prereq=db.get(Commitment,dep.prerequisite_id)
                if prereq and prereq.status!="done": add_finding(db,scenario.id,"dependency_blocker",[prereq.id],[prereq.utterance_id] if prereq.utterance_id else [],f"Prerequisite '{prereq.action_text}' is not complete.")
            else: add_finding(db,scenario.id,"unknown",[],loads(dep.evidence_ids_json),f"External prerequisite is unresolved: {dep.prerequisite_text}")
    scenario.status="evaluated"; scenario.ledger_version=get_ledger_version(db); scenario.updated_at=utc_now()
    db.commit(); db.refresh(scenario)
    from app.ai.whatif_graph import explain_scenario
    result=explain_scenario(db,scenario_dict(db,scenario))
    scenario.explanation=result["paragraph"]; scenario.explanation_source=result["source"]; db.commit(); db.refresh(scenario)
    return {**scenario_dict(db,scenario),"risk_level":result["risk_level"],"related_commitments":result["related_commitments"],
            "ai_error":result["ai_error"]}
def datetime_value(value):
    if not value: return None
    from datetime import datetime
    return as_utc(datetime.fromisoformat(value.replace("Z","+00:00")))
def prepare_change(db,scenario_id,ttl_minutes=30):
    scenario=get_scenario(db,scenario_id)
    if scenario.status!="evaluated": raise PlanningError("Evaluate the scenario before preparing it")
    current=get_ledger_version(db)
    if scenario.ledger_version!=current: raise PlanningError("Ledger changed; evaluate the scenario again",409)
    old=db.query(PreparedChange).filter_by(scenario_id=scenario.id,status="pending").all()
    for item in old: item.status="superseded"
    payload={"operation":scenario.operation,"target_commitment_id":scenario.target_commitment_id,"changes":loads(scenario.proposed_change_json)}
    prepared=PreparedChange(scenario_id=scenario.id,exact_payload_json=dumps(payload),expected_ledger_version=current,
        expires_at=utc_now()+timedelta(minutes=ttl_minutes),status="pending",idempotency_key=secrets.token_hex(24))
    db.add(prepared); scenario.status="prepared"; scenario.updated_at=utc_now(); db.commit(); db.refresh(prepared); return prepared_dict(prepared)
def confirm_change(db,change_id):
    prepared=db.get(PreparedChange,change_id)
    if not prepared: raise PlanningError("Prepared change not found",404)
    if prepared.status=="executed":
        item=db.get(Commitment,prepared.result_commitment_id) if prepared.result_commitment_id else None
        return {"status":"executed","already_executed":True,"commitment":serialize_commitment(db,item) if item else None}
    if prepared.status!="pending": raise PlanningError(f"Prepared change is {prepared.status}",409)
    if as_utc(prepared.expires_at)<utc_now(): prepared.status="expired"; db.commit(); raise PlanningError("Prepared change expired",409)
    if prepared.expected_ledger_version!=get_ledger_version(db): raise PlanningError("Ledger changed; re-evaluate and prepare again",409)
    scenario=get_scenario(db,prepared.scenario_id); payload=loads(prepared.exact_payload_json); changes=payload["changes"]
    for key in ("due_at","starts_at","ends_at"):
        if key in changes: changes[key]=datetime_value(changes[key])
    now=utc_now()
    if payload["operation"]=="add":
        if not (changes.get("action_text") or "").strip(): raise PlanningError("add requires action_text")
        item=Commitment(action_text=changes.get("action_text", "").strip(),counterparty=changes.get("counterparty"),
            due_text=changes.get("due_text"),due_at=changes.get("due_at"),starts_at=changes.get("starts_at"),
            ends_at=changes.get("ends_at"),timezone_name=changes.get("timezone_name"),status=changes.get("status") or "open")
        db.add(item); db.flush(); before={}
    else:
        item=db.get(Commitment,payload["target_commitment_id"])
        if not item: raise PlanningError("Target commitment no longer exists",409)
        before=commitment_values(item); validated=validate_changes(item,changes)
        old=item.status
        for key,value in validated.items(): setattr(item,key,value)
        if old!="done" and item.status=="done": item.completed_at=now
        elif old=="done" and item.status!="done": item.completed_at=None
        item.version+=1
    db.add(CommitmentRevision(commitment_id=item.id,previous_values_json=dumps(before),proposed_values_json=dumps(commitment_values(item)),
        evidence_ids_json=dumps([item.utterance_id] if item.utterance_id else []),review_status="approved",approved_at=now))
    bump_ledger_version(db); prepared.status="executed"; prepared.executed_at=now; prepared.result_commitment_id=item.id
    scenario.status="confirmed"; scenario.updated_at=now
    try: db.commit(); db.refresh(item)
    except Exception: db.rollback(); raise
    return {"status":"executed","already_executed":False,"commitment":serialize_commitment(db,item)}
def cancel_change(db,change_id):
    item=db.get(PreparedChange,change_id)
    if not item: raise PlanningError("Prepared change not found",404)
    if item.status=="executed": raise PlanningError("Executed change cannot be cancelled",409)
    if item.status=="pending": item.status="cancelled"; scenario=get_scenario(db,item.scenario_id); scenario.status="cancelled"; scenario.updated_at=utc_now(); db.commit()
    return prepared_dict(item)
