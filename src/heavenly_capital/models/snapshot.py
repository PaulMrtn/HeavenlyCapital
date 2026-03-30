from dataclasses import dataclass, asdict
from typing import Optional
import time

@dataclass
class SessionSnapshot:
    session_id: str
    date: str
    phase: str
    status: str
    state: str
    error: bool

@dataclass
class KernelSnapshot:
    timestamp: float
    market_state: str
    today_session: Optional[SessionSnapshot]
    db_status: str

    def as_dict(self):
        return asdict(self)





# Méthode à ajouter dans Kernel
def snapshot(self) -> KernelSnapshot:
    today_snap = None

    if self._today_session:
        today_snap = SessionSnapshot(
            session_id=str(self._today_session.session_id),
            date=str(self._today_session.session_date),
            phase=str(self._today_session.phase),
            status=str(self._today_session.status),
            state=str(self._today_session.state),
            error=self._today_session.error
        )

    return KernelSnapshot(
        timestamp=time.time(),
        market_state=str(self._market_clock.state),
        today_session=today_snap,
        db_status="connected" if self._db else "disconnected"
    )