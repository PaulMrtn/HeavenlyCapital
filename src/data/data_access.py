from __future__ import annotations

from typing import Protocol, Optional, TYPE_CHECKING
from datetime import date

if TYPE_CHECKING:
    from src.core.system_manager import MarketDaySession


class DataAccessLayer(Protocol):

    def get_by_date(self, session_date: date) -> Optional["MarketDaySession"]: ...
    def exists_for_date(self, session_date: date) -> bool: ...


class InMemoryMarketDaySessionDAL:
    def __init__(self):
        self._store = None

    def get_by_date(self, session_date: date) -> Optional["MarketDaySession"]:
        return self._store.get(session_date)

    def exists_for_date(self, session_date: date) -> bool:
        return session_date in self._store
