from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from datetime import date

if TYPE_CHECKING:
    from src.core.system_manager import TradingSession

class DataIngestionLayer(Protocol):

    def insert(self, session: "TradingSession") -> None: ...
    def update(self, session: "TradingSession") -> None: ...
    def exists_for_date(self, session_date: date) -> bool: ...


class InMemoryTradingSessionDIL:
    """Mock DIL: écriture en mémoire."""
    def __init__(self):
        self._store = None

    def insert(self, session: "TradingSession") -> None:
        # comportement simple: refuse d'écraser
        if session.session_date in self._store:
            raise ValueError("TradingSession déjà existante pour cette date")
        self._store[session.session_date] = session

    def update(self, session: "TradingSession") -> None:
        self._store[session.session_date] = session

    def exists_for_date(self, session_date: date) -> bool:
        return session_date in self._store
