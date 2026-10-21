from sqlalchemy.orm import Session

from app.models_planning import LedgerState
from app.services.timeutil import utc_now


def get_ledger_version(db: Session) -> int:
    state = db.get(LedgerState, 1)
    if state is None:
        state = LedgerState(id=1, version=0, updated_at=utc_now())
        db.add(state); db.flush()
    return state.version

def bump_ledger_version(db: Session) -> int:
    state = db.get(LedgerState, 1)
    if state is None:
        state = LedgerState(id=1, version=1, updated_at=utc_now()); db.add(state)
    else:
        state.version += 1; state.updated_at = utc_now()
    db.flush(); return state.version
