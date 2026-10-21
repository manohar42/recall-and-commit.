import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.ai import router as ai_router
from app.api.assistant import router as assistant_router
from app.api.commitments import router as commitments_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.planning import router as planning_router
from app.api.recall import router as recall_router
from app.config import BACKEND_DIR, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recall_commit")


def run_migrations() -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_migrate:
        run_migrations()
    logger.info("Recall & Commit starting | AI mode: %s | model: %s", "gemini" if settings.ai_configured else "rules_fallback",
                settings.gemini_model)
    yield
    logger.info("Recall & Commit stopping")


def create_app() -> FastAPI:
    app = FastAPI(title="Recall & Commit API", version="2.0.0", lifespan=lifespan,
                  description="Evidence-backed recall, AI-reviewed commitments, and safe What If planning "
                              "(LangChain + LangGraph + Google Gemini).")
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        details = [{k: v for k, v in e.items() if k != "ctx"} for e in exc.errors()]
        message = "; ".join(f"{'.'.join(str(p) for p in d.get('loc', []))}: {d.get('msg')}" for d in details[:3])
        return JSONResponse(status_code=422, content={"detail": message or "Invalid request", "error": {
            "code": "VALIDATION_ERROR", "message": "The request contains invalid data.",
            "request_id": getattr(request.state, "request_id", None), "details": jsonable_encoder(details)}})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        logger.exception("Unhandled request error id=%s", getattr(request.state, "request_id", None))
        return JSONResponse(status_code=500, content={"detail": f"Server error: {exc}", "error": {
            "code": "INTERNAL_ERROR", "message": "An unexpected server error occurred.",
            "request_id": getattr(request.state, "request_id", None)}})

    @app.get("/", tags=["System"])
    def root():
        return {"message": "Recall & Commit API is running", "docs": "/docs", "ai_status": "/api/ai/status"}

    for router in (health_router, ai_router, imports_router, conversations_router, recall_router, commitments_router,
                   planning_router, assistant_router):
        app.include_router(router)
    return app


app = create_app()
