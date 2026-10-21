from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.llm import ai_status
from app.schemas.commitments import AnalysisStatus, AnalyzeSummary
from app.services.commitments import analysis_status, analyze_pending
from app.storage import get_db

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.get("/status")
@router.get("/config")
def status():
    """AI configuration as seen by the backend. The API key itself is never returned."""
    return ai_status()


@router.get("/commitments/status", response_model=AnalysisStatus)
def commitment_status(db: Session = Depends(get_db)):
    return analysis_status(db)


@router.post("/commitments/analyze", response_model=AnalyzeSummary)
def analyze(limit: int | None = Query(None, ge=1, le=200), db: Session = Depends(get_db)):
    """Analyze the next batch of un-reviewed conversations. Call repeatedly until remaining == 0."""
    return analyze_pending(db, limit)
