import json

from sqlalchemy.orm import Session

from app.models_commitments import Commitment
from app.models_planning import CommitmentDependency, CommitmentRevision
from app.services.timeutil import as_utc


class DependencyError(Exception):
    def __init__(self,message,status_code=422): super().__init__(message); self.status_code=status_code

def creates_cycle(db:Session,dependent_id:int,prerequisite_id:int)->bool:
    graph={}
    for edge in db.query(CommitmentDependency).filter_by(review_status="approved"):
        if edge.prerequisite_id: graph.setdefault(edge.dependent_id,set()).add(edge.prerequisite_id)
    graph.setdefault(dependent_id,set()).add(prerequisite_id)
    stack=[prerequisite_id]; seen=set()
    while stack:
        node=stack.pop()
        if node==dependent_id: return True
        if node in seen: continue
        seen.add(node); stack.extend(graph.get(node,()))
    return False

def serialize_dependency(item):
    return {"id":item.id,"dependent_id":item.dependent_id,"prerequisite_id":item.prerequisite_id,
        "prerequisite_text":item.prerequisite_text,"evidence_ids":json.loads(item.evidence_ids_json),
        "review_status":item.review_status,"created_at":as_utc(item.created_at)}

def create_dependency(db:Session,payload):
    if not db.get(Commitment,payload.dependent_id): raise DependencyError("Dependent commitment not found",404)
    if payload.prerequisite_id:
        if not db.get(Commitment,payload.prerequisite_id): raise DependencyError("Prerequisite commitment not found",404)
        if creates_cycle(db,payload.dependent_id,payload.prerequisite_id): raise DependencyError("Dependency would create a cycle")
    item=CommitmentDependency(dependent_id=payload.dependent_id,prerequisite_id=payload.prerequisite_id,
        prerequisite_text=payload.prerequisite_text,evidence_ids_json=json.dumps(payload.evidence_ids),review_status="approved")
    db.add(item)
    try: db.commit(); db.refresh(item)
    except Exception as exc: db.rollback(); raise DependencyError("Dependency already exists or is invalid",409) from exc
    return serialize_dependency(item)

def list_dependencies(db:Session,commitment_id:int):
    return [serialize_dependency(x) for x in db.query(CommitmentDependency).filter_by(dependent_id=commitment_id).order_by(CommitmentDependency.id)]

def list_revisions(db:Session,commitment_id:int):
    if not db.get(Commitment,commitment_id): raise DependencyError("Commitment not found",404)
    return [{"id":x.id,"commitment_id":x.commitment_id,"previous_values":json.loads(x.previous_values_json),
        "proposed_values":json.loads(x.proposed_values_json),"evidence_ids":json.loads(x.evidence_ids_json),
        "review_status":x.review_status,"created_at":as_utc(x.created_at),"approved_at":as_utc(x.approved_at)}
        for x in db.query(CommitmentRevision).filter_by(commitment_id=commitment_id).order_by(CommitmentRevision.id.desc())]
