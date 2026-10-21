from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.ai.llm import ai_status
from app.storage import check_database_connection

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
@router.get("/", include_in_schema=False)
def health_check() -> dict:
    return {"status": "ok", "service": "recall-and-commit-api", "version": "2.0.0"}


@router.get("/ready")
def readiness_check() -> JSONResponse:
    ok = check_database_connection()
    return JSONResponse(status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"status": "ready" if ok else "not_ready", "checks": {"database": "ok" if ok else "unavailable"}})


@router.get("/ai")
def ai_health() -> dict:
    return ai_status()
