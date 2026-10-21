from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.schemas.imports import ImportSummaryResponse, SampleImportPayload
from app.services.ingestion import import_sample_payload
from app.services.recall import rebuild_recall_index
from app.services.sample_loader import load_sample_payload, normalize_payload, resolve_sample_path
from app.storage import get_db

router = APIRouter(prefix="/api/imports", tags=["Imports"])


@router.get("/sample/info")
def sample_info():
    try:
        path = resolve_sample_path()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    payload = load_sample_payload(path)
    return {"path": str(path), "conversations": len(payload.conversations),
            "utterances": sum(len(c.utterances) for c in payload.conversations)}


@router.post("/sample", response_model=ImportSummaryResponse)
def sample(db: Session = Depends(get_db)):
    try:
        payload = load_sample_payload()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, f"Sample file is not valid: {exc}") from exc
    result = import_sample_payload(db, payload)
    rebuild_recall_index(db)
    return result


@router.post("/json", response_model=ImportSummaryResponse)
def json_import(raw: Any = Body(...), db: Session = Depends(get_db)):
    """Accepts {schema_version, source, conversations:[...]} or a plain list (older formats are converted)."""
    try:
        payload = SampleImportPayload.model_validate(normalize_payload(raw))
    except (ValueError, ValidationError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"Invalid conversations JSON: {exc}") from exc
    result = import_sample_payload(db, payload)
    rebuild_recall_index(db)
    return result
