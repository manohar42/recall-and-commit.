from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.recall_graph import answer_question
from app.schemas.recall import RecallRequest, RecallResponse
from app.storage import get_db

router = APIRouter(prefix="/api/recall", tags=["Recall"])


@router.post("", response_model=RecallResponse)
def recall(body: RecallRequest, db: Session = Depends(get_db)):
    return answer_question(db, body.question, body.limit)
