"""Loads the bundled sample file. Accepts the import schema and both older list formats."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import BACKEND_DIR, get_settings
from app.schemas.imports import SampleImportPayload

CANDIDATE_DIRS = ("sample_data", "Sample_data", "Sample-data", "sample-data")


def resolve_sample_path(explicit: str | Path | None = None) -> Path:
    """Find the sample file, tolerating the folder-name variants that caused earlier failures."""
    if explicit:
        path = Path(explicit)
        if path.exists():
            return path
        raise FileNotFoundError(f"Sample data file not found at: {path.resolve()}")
    configured = Path(get_settings().sample_data_path)
    if configured.exists():
        return configured
    for name in CANDIDATE_DIRS:
        candidate = BACKEND_DIR / name / "conversations.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Sample data file not found at: {configured}. Put conversations.json in backend/sample_data/.")


def normalize_payload(raw) -> dict:
    """Convert any supported JSON shape into the SampleImportPayload shape."""
    if isinstance(raw, dict) and "conversations" in raw:
        raw.setdefault("schema_version", "1.0")
        raw.setdefault("source", "sample")
        return raw
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError("Unsupported JSON: expected an object with 'conversations' or a list of conversations.")
    conversations = []
    for i, item in enumerate(raw, 1):
        if "utterances" in item and "started_at" in item:  # already new-style list item
            item = dict(item)
            item.setdefault("external_id", item.get("id") or f"conv-{i:04d}")
            item.setdefault("participants", sorted({u["speaker"] for u in item["utterances"]}))
            item["utterances"] = [
                {"sequence": u.get("sequence", n), "speaker": u["speaker"], "text": u["text"],
                 "occurred_at": u.get("occurred_at") or u.get("timestamp")}
                for n, u in enumerate(item["utterances"], 1)
            ]
            speakers = {u["speaker"] for u in item["utterances"]}
            item.setdefault("user_speaker", "Alex" if "Alex" in speakers else None)
            conversations.append(item)
            continue
        # legacy format: external/day/hour/people/lines
        started = datetime(2026, 10, int(item["day"]), int(item["hour"]), tzinfo=UTC)
        lines = item["lines"]
        speakers = {s for s, _ in lines}
        conversations.append({
            "external_id": item["external"], "title": item["title"], "started_at": started.isoformat(),
            "participants": item.get("people") or sorted(speakers),
            "user_speaker": "Alex" if "Alex" in speakers else None,
            "utterances": [{"sequence": n, "speaker": s, "text": t,
                            "occurred_at": (started + timedelta(seconds=40 * (n - 1))).isoformat()}
                           for n, (s, t) in enumerate(lines, 1)],
        })
    return {"schema_version": "1.0", "source": "sample", "conversations": conversations}


def read_raw(path: Path):
    with path.open(encoding="utf-8-sig") as file:
        return json.load(file)


def load_sample_payload(path: str | Path | None = None) -> SampleImportPayload:
    return SampleImportPayload.model_validate(normalize_payload(read_raw(resolve_sample_path(path))))
