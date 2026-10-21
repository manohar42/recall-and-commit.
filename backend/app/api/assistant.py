from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.planning import AssistantMessageRequest, AssistantMessageResponse
from app.services.assistant import handle_message
from app.services.planning import PlanningError
from app.storage import get_db

router=APIRouter(prefix="/api/assistant",tags=["Alexa+ Simulation"])
@router.post("/messages",response_model=AssistantMessageResponse)
def message(body:AssistantMessageRequest,db:Session=Depends(get_db)):
    try: return handle_message(db,body)
    except PlanningError as exc: raise HTTPException(exc.status_code,str(exc)) from exc
