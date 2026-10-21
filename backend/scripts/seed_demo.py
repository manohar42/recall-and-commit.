"""Seed the database from sample_data/conversations.json (same import path as the UI button).

Examples (run from the backend folder, or inside Docker with `docker compose exec api ...`):
    python -m scripts.seed_demo                     # reset + import + pre-approved ledger entries
    python -m scripts.seed_demo --analyze           # ...and run the AI commitment review on every conversation
    python -m scripts.seed_demo --file other.json --keep-existing
"""
import argparse
from pathlib import Path

from sqlalchemy import text

from app.main import run_migrations
from app.models import Conversation, Utterance
from app.models_commitments import Commitment, CommitmentCandidate, ConversationAIReview
from app.models_planning import (
    AssistantSession,
    CommitmentDependency,
    CommitmentRevision,
    LedgerState,
    PlanningScenario,
    PreparedChange,
    ScenarioFinding,
)
from app.schemas.imports import SampleImportPayload
from app.services.commitments import analyze_pending
from app.services.ingestion import import_sample_payload
from app.services.ledger import bump_ledger_version
from app.services.recall import rebuild_recall_index
from app.services.sample_loader import normalize_payload, read_raw, resolve_sample_path
from app.services.timeutil import parse_iso, utc_now
from app.storage import SessionLocal

RESET_ORDER = (AssistantSession, PreparedChange, ScenarioFinding, PlanningScenario, CommitmentDependency,
               CommitmentRevision, Commitment, CommitmentCandidate, ConversationAIReview, Utterance, Conversation)


def reset(db) -> None:
    db.query(AssistantSession).update({AssistantSession.active_scenario_id: None})
    for model in RESET_ORDER:
        db.query(model).delete()
    state = db.get(LedgerState, 1)
    if state:
        state.version = 0
    db.execute(text("DELETE FROM recall_fts"))
    db.commit()


def add_ledger_entries(db, raw: dict, source: str) -> tuple[int, int]:
    created = done = 0
    by_action = {}
    for item in raw.get("conversations", []):
        seeds = item.get("seed_commitments") or []
        if not seeds:
            continue
        conv = db.query(Conversation).filter_by(source_type=source, external_id=item["external_id"]).first()
        if not conv:
            continue
        lines = {u.sequence: u for u in conv.utterances}
        for s in seeds:
            u = lines.get(s["utterance_sequence"])
            if not u or u.speaker != conv.user_speaker:
                print(f"  ! skipped seed in {item['external_id']}: line {s['utterance_sequence']} is not the user's line")
                continue
            if db.query(CommitmentCandidate).filter_by(utterance_id=u.id).first():
                continue
            starts, ends, due = parse_iso(s.get("starts_at")), parse_iso(s.get("ends_at")), parse_iso(s.get("due_at"))
            cand = CommitmentCandidate(
                conversation_id=conv.id, utterance_id=u.id, utterance_sequence=u.sequence, speaker=u.speaker,
                source_text=u.text, action_text=s["action_text"], counterparty=s.get("counterparty"),
                due_text=s.get("due_text"), due_at=due, starts_at=starts, ends_at=ends, confidence=0.95,
                status="approved", ai_label="commitment", analysis_source="seed",
                ai_explanation="Pre-approved demo entry from the sample file.", reviewed_at=conv.started_at)
            db.add(cand)
            db.flush()
            status = s.get("status", "open")
            c = Commitment(candidate_id=cand.id, conversation_id=conv.id, utterance_id=u.id, action_text=s["action_text"],
                           counterparty=s.get("counterparty"), due_text=s.get("due_text"), due_at=due or ends,
                           starts_at=starts, ends_at=ends, timezone_name="America/Phoenix", status=status,
                           completed_at=(ends or due or utc_now()) if status == "done" else None)
            db.add(c)
            db.flush()
            by_action[s["action_text"]] = c
            created += 1
            done += status == "done"
    # A demo dependency: the dinner depends on picking up the cake first.
    dinner = next((c for a, c in by_action.items() if "birthday dinner" in a.lower()), None)
    cake = next((c for a, c in by_action.items() if "cake" in a.lower()), None)
    if dinner and cake:
        db.add(CommitmentDependency(dependent_id=dinner.id, prerequisite_id=cake.id, evidence_ids_json="[]",
                                    review_status="approved"))
    return created, done


def seed(path: Path | None, keep_existing: bool, with_ledger: bool, analyze: bool) -> None:
    run_migrations()
    file_path = resolve_sample_path(path)
    raw = normalize_payload(read_raw(file_path))
    payload = SampleImportPayload.model_validate(raw)
    print(f"Loaded {len(payload.conversations)} conversations from {file_path}")
    with SessionLocal() as db:
        if not keep_existing:
            reset(db)
        summary = import_sample_payload(db, payload)
        ledger, done = add_ledger_entries(db, raw, payload.source) if with_ledger else (0, 0)
        bump_ledger_version(db)
        db.commit()
        excerpts = rebuild_recall_index(db)
        print(f"Imported: {summary.conversations_created} created, {summary.conversations_updated} updated, "
              f"{summary.conversations_skipped} unchanged, {summary.utterances_created} utterances, "
              f"{excerpts} recall excerpts indexed.")
        print(f"Ledger: {ledger} pre-approved commitments ({done} done, {ledger - done} open).")
        if analyze:
            total = 0
            while True:
                r = analyze_pending(db, 10)
                total += r["candidates_created"]
                print(f"  AI review ({r['source']}): analyzed {r['analyzed']}, failed {r['failed']}, "
                      f"remaining {r['remaining']}, new candidates {r['candidates_created']}")
                if r["errors"]:
                    print("  ! " + " | ".join(r["errors"]))
                if r["remaining"] == 0 or r["analyzed"] == 0:
                    break
            print(f"Review inbox: {total} new candidates waiting for approval.")
        else:
            print("Next: open the app > Review inbox > 'Analyze with AI' (or rerun with --analyze).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Recall & Commit from a conversations JSON file.")
    parser.add_argument("--file", default=None, help="Path to conversations.json (default: backend/sample_data/conversations.json)")
    parser.add_argument("--keep-existing", action="store_true", help="Do not delete existing data first")
    parser.add_argument("--no-ledger", action="store_true", help="Skip the pre-approved demo commitments")
    parser.add_argument("--analyze", action="store_true", help="Run the AI commitment review after importing")
    args = parser.parse_args()
    seed(Path(args.file) if args.file else None, args.keep_existing, not args.no_ledger, args.analyze)
