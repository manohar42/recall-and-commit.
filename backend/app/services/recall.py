import re

from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.models import Conversation

WINDOW = 4  # utterances per excerpt
STEP = 2    # overlapping windows so an answer is never split across two excerpts

STOP_WORDS = {
    "a", "about", "an", "and", "any", "are", "as", "at", "be", "but", "by", "can", "did", "do", "does", "for",
    "from", "had", "has", "have", "how", "i", "if", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our",
    "should", "so", "than", "that", "the", "their", "then", "there", "this", "to", "was", "we", "were", "what",
    "when", "where", "which", "who", "why", "will", "with", "would", "you", "your", "tell", "told", "say", "said", "decide", "decided", "get", "got", "know", "remember",
}


def rebuild_recall_index(db: Session) -> int:
    db.execute(text("DROP TABLE IF EXISTS recall_fts"))
    db.execute(text("""CREATE VIRTUAL TABLE IF NOT EXISTS recall_fts USING fts5(
            conversation_id UNINDEXED, conversation_title, sequence_start UNINDEXED,
            sequence_end UNINDEXED, excerpt, tokenize='porter unicode61')"""))
    inserted = 0
    for conversation in db.query(Conversation).options(selectinload(Conversation.utterances)).all():
        utterances = sorted(conversation.utterances, key=lambda u: u.sequence)
        starts = list(range(0, max(len(utterances) - WINDOW, 0) + 1, STEP)) or [0]
        if utterances and starts[-1] + WINDOW < len(utterances):
            starts.append(len(utterances) - WINDOW)
        for start in starts:
            group = utterances[start:start + WINDOW]
            if not group:
                continue
            db.execute(text("""INSERT INTO recall_fts (conversation_id, conversation_title, sequence_start, sequence_end, excerpt)
                               VALUES (:cid, :title, :s, :e, :x)"""),
                       {"cid": conversation.id, "title": conversation.title, "s": group[0].sequence,
                        "e": group[-1].sequence, "x": "\n".join(f"{u.speaker}: {u.text}" for u in group)})
            inserted += 1
    db.commit()
    return inserted


def keywords(question: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", question.lower())
    return list(dict.fromkeys(w for w in words if w not in STOP_WORDS and len(w) > 1))


def _make_fts_query(question: str) -> str:
    terms = []
    for w in keywords(question):
        terms.append(f'"{w}"')
        if len(w) >= 5:
            terms.append(f'"{w}"*')
    return " OR ".join(dict.fromkeys(terms))


def search_recall(db: Session, question: str, limit: int) -> list[dict]:
    query = _make_fts_query(question)
    if not query:
        return []
    rows = db.execute(text("""SELECT conversation_id, conversation_title, sequence_start, sequence_end, excerpt,
                                     bm25(recall_fts) AS score
                              FROM recall_fts WHERE recall_fts MATCH :q ORDER BY score LIMIT :n"""),
                      {"q": query, "n": limit * 3}).mappings()
    results, seen_conversations = [], {}
    for row in rows:
        cid = int(row["conversation_id"])
        if seen_conversations.get(cid, 0) >= 2:  # keep variety across conversations
            continue
        seen_conversations[cid] = seen_conversations.get(cid, 0) + 1
        results.append({**dict(row), "conversation_id": cid, "sequence_start": int(row["sequence_start"]),
                        "sequence_end": int(row["sequence_end"])})
        if len(results) >= limit:
            break
    dates = {c.id: c.started_at for c in db.query(Conversation).filter(Conversation.id.in_(seen_conversations)).all()}
    for r in results:
        r["started_at"] = dates.get(r["conversation_id"])
    return results
