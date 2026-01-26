from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional


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
class TickEvent:
    req_id: int
    tick_type: int
    price: Optional[float] = None
    size: Optional[int] = None
    ts_gateway: datetime = datetime.now(tz=timezone.utc)
