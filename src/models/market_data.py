from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from src.models.tickers import AssetType

@dataclass(frozen=True)
class MarketDataInstrument:
    internal_code: str
    symbol: str
    asset_type: AssetType

@dataclass(frozen=True)
class MarketTick:
    symbol: str
    ts: datetime
    last: float
    bid: float
    ask: float

