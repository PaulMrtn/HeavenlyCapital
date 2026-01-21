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

@dataclass(frozen=True)
class MarketTick:
    symbol: str
    ts: datetime
    last: float
    bid: float
    ask: float

