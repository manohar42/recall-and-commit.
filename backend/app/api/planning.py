from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.planning import (
    ConfirmationOut,
    PreparedChangeOut,
    ScenarioCreate,
    ScenarioOut,
)
from app.services.planning import (
    PlanningError,
    cancel_change,
    confirm_change,
    create_scenario,
    evaluate_scenario,
    get_scenario,
    prepare_change,
    scenario_dict,
)
from app.storage import get_db

router=APIRouter(tags=["What If Planning"])
def run(call):
    try: return call()
    except PlanningError as exc: raise HTTPException(exc.status_code,str(exc)) from exc
@router.post("/api/scenarios",response_model=ScenarioOut,status_code=201)
def create(body:ScenarioCreate,db:Session=Depends(get_db)): return run(lambda:create_scenario(db,body))
@router.get("/api/scenarios/{scenario_id}",response_model=ScenarioOut)
def get(scenario_id:int,db:Session=Depends(get_db)): return run(lambda:scenario_dict(db,get_scenario(db,scenario_id)))
@router.post("/api/scenarios/{scenario_id}/evaluate",response_model=ScenarioOut)
def evaluate(scenario_id:int,db:Session=Depends(get_db)): return run(lambda:evaluate_scenario(db,scenario_id))
@router.post("/api/scenarios/{scenario_id}/prepare-change",response_model=PreparedChangeOut)
def prepare(scenario_id:int,ttl_minutes:int=Query(30,ge=1,le=1440),db:Session=Depends(get_db)): return run(lambda:prepare_change(db,scenario_id,ttl_minutes))
@router.post("/api/commitment-changes/{change_id}/confirm",response_model=ConfirmationOut)
def confirm(change_id:int,db:Session=Depends(get_db)): return run(lambda:confirm_change(db,change_id))
@router.post("/api/commitment-changes/{change_id}/cancel",response_model=PreparedChangeOut)
def cancel(change_id:int,db:Session=Depends(get_db)): return run(lambda:cancel_change(db,change_id))
