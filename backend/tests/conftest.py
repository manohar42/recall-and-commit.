import os

os.environ["AUTO_MIGRATE"] = "false"
os.environ["GOOGLE_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
import app.models_commitments  # noqa: E402,F401
import app.models_planning  # noqa: E402,F401
from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.storage import Base, get_db  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("CREATE VIRTUAL TABLE recall_fts USING fts5(conversation_id UNINDEXED, conversation_title,"
                       " sequence_start UNINDEXED, sequence_end UNINDEXED, excerpt, tokenize='porter unicode61')"))
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c


class FakeStructured:
    def __init__(self, responder, schema):
        self.responder, self.schema = responder, schema

    def invoke(self, messages):
        return self.responder(self.schema, messages)


class FakeGemini:
    """Stands in for ChatGoogleGenerativeAI: same with_structured_output().invoke() interface."""

    def __init__(self, responder):
        self.responder = responder
        self.calls = 0

    def with_structured_output(self, schema, **_):
        self.calls += 1
        return FakeStructured(self.responder, schema)


@pytest.fixture()
def fake_gemini(monkeypatch):
    def install(responder):
        settings = get_settings()
        monkeypatch.setattr(settings, "google_api_key", "test-key")
        model = FakeGemini(responder)
        for module in ("app.ai.commitment_graph", "app.ai.recall_graph", "app.ai.whatif_graph"):
            monkeypatch.setattr(f"{module}.get_chat_model", lambda: model)
        return model
    return install
