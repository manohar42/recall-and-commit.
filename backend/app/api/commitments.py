from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models import Conversation
from app.models_commitments import CommitmentCandidate
from app.schemas.commitments import (
    AnalyzeSummary,
    ApproveRequest,
    CandidateOut,
    CommitmentOut,
    CommitmentPatch,
    EvidenceIssue,
    ReviewSummary,
)
from app.schemas.planning import DependencyCreate, DependencyOut, RevisionOut
from app.services import commitments as svc
from app.services.commitment_review import (
    get_review_summary,
    list_commitments,
    patch_commitment,
    serialize_commitment,
)
from app.services.dependencies import (
    DependencyError,
    create_dependency,
    list_dependencies,
    list_revisions,
)
from app.services.evidence import check_evidence
from app.storage import get_db

router=APIRouter(prefix="/api/commitments",tags=["Commitments"])
def fail(exc)->NoReturn: raise HTTPException(status_code=exc.status_code,detail=str(exc))
def _with_titles(db,items):
    titles={c.id:c.title for c in db.query(Conversation).filter(Conversation.id.in_({i.conversation_id for i in items}))}
    return [{**CandidateOut.model_validate(i).model_dump(),"conversation_title":titles.get(i.conversation_id)} for i in items]
@router.post("/detect",response_model=AnalyzeSummary)
def detect(limit:int|None=Query(None,ge=1,le=200),db:Session=Depends(get_db)):
    """Kept for compatibility: runs the AI commitment review (same as POST /api/ai/commitments/analyze)."""
    return svc.analyze_pending(db,limit)
@router.get("/candidates",response_model=list[CandidateOut])
def candidates(status:str=Query("pending",pattern="^(pending|approved|rejected)$"),db:Session=Depends(get_db)):
    return _with_titles(db,db.query(CommitmentCandidate).filter_by(status=status).order_by(CommitmentCandidate.due_at.is_(None),CommitmentCandidate.due_at,CommitmentCandidate.id).all())
@router.get("/candidates/misattributed",response_model=list[CandidateOut])
def misattributed(db:Session=Depends(get_db)): return _with_titles(db,svc.list_misattributed_candidates(db))
@router.post("/candidates/{candidate_id}/approve",response_model=CommitmentOut)
def approve(candidate_id:int,body:ApproveRequest|None=None,db:Session=Depends(get_db)):
    try: item=svc.approve_candidate(db,candidate_id,body.model_dump(exclude_unset=True) if body else {})
    except svc.ReviewError as exc: fail(exc)
    return serialize_commitment(db,item)
@router.post("/candidates/{candidate_id}/reject",response_model=CandidateOut)
def reject(candidate_id:int,db:Session=Depends(get_db)):
    try: return _with_titles(db,[svc.reject_candidate(db,candidate_id)])[0]
    except svc.ReviewError as exc: fail(exc)
@router.get("/review",response_model=ReviewSummary)
def review(soon_days:int=Query(7,ge=1,le=30),completed_days:int=Query(7,ge=1,le=90),db:Session=Depends(get_db)): return get_review_summary(db,soon_days,completed_days)
@router.get("/evidence-check",response_model=list[EvidenceIssue])
def evidence(db:Session=Depends(get_db)): return check_evidence(db)
@router.get("",response_model=list[CommitmentOut])
def ledger(status:str|None=Query(None,pattern="^(open|done|cancelled)$"),due:str|None=Query(None,pattern="^(overdue|soon|undated|later)$"),limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db)): return list_commitments(db,status,due,limit)
@router.patch("/{commitment_id}",response_model=CommitmentOut)
def patch(commitment_id:int,body:CommitmentPatch,db:Session=Depends(get_db)):
    changes=body.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422,"Provide at least one field to update")
    try: result=patch_commitment(db,commitment_id,changes)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    if not result: raise HTTPException(404,"Commitment not found")
    return result
@router.get("/{commitment_id}/history",response_model=list[RevisionOut])
def history(commitment_id:int,db:Session=Depends(get_db)):
    try: return list_revisions(db,commitment_id)
    except DependencyError as exc: fail(exc)
@router.get("/{commitment_id}/dependencies",response_model=list[DependencyOut])
def dependencies(commitment_id:int,db:Session=Depends(get_db)): return list_dependencies(db,commitment_id)
@router.post("/dependencies",response_model=DependencyOut,status_code=201)
def dependency(body:DependencyCreate,db:Session=Depends(get_db)):
    try: return create_dependency(db,body)
    except DependencyError as exc: fail(exc)
