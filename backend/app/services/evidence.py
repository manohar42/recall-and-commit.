from sqlalchemy.orm import Session

from app.models import Conversation, Utterance
from app.models_commitments import Commitment, CommitmentCandidate


def check_one(db,kind,record,sequence=None,text=None):
    out=[]
    def add(code,detail): out.append({"record_type":kind,"record_id":record.id,"code":code,"detail":detail})
    utterance=db.get(Utterance,record.utterance_id) if record.utterance_id else None
    if not utterance: add("missing_utterance",f"utterance {record.utterance_id} not found"); return out
    if not db.get(Conversation,record.conversation_id): add("missing_conversation",f"conversation {record.conversation_id} not found")
    if utterance.conversation_id!=record.conversation_id: add("conversation_mismatch","utterance belongs to another conversation")
    if sequence is not None and utterance.sequence!=sequence: add("sequence_mismatch","stored sequence differs from source")
    if text is not None and utterance.text!=text: add("text_changed","source text differs from candidate evidence")
    return out

def check_evidence(db:Session):
    issues=[]
    for c in db.query(CommitmentCandidate): issues+=check_one(db,"candidate",c,c.utterance_sequence,c.source_text)
    for c in db.query(Commitment):
        if c.utterance_id: issues+=check_one(db,"commitment",c)
    return issues
