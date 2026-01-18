from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from datetime import date

if TYPE_CHECKING:
    from src.core.system_manager import MarketDaySession

class DataIngestionLayer(Protocol):
    pass

class InMemorySessionDIL:
    def __init__(self):
        self._store = None