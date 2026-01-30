from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum



class AssetType(StrEnum):
    STK = "STK"
    OPT = "OPT"
    CASH = "CASH"


@dataclass(frozen=True)
class MarketDataInstrument:
    asset_id: str
    symbol: str
    asset_type: AssetType


@dataclass(slots=True, frozen=True)
class TickEvent:
    symbol: str
    conId: int
    last: float
    last_size: float
    bid: float
    bid_size: float
    ask: float
    ask_size: float
    volume: float
    timestamp: float

