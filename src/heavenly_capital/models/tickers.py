from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from heavenly_capital.models.market_data import AssetType


@dataclass(frozen=True)
class TickerUniverseSnapshot:
    asset_id: str
    symbol: str
    asset_type: AssetType
    tickers: list[str]
    updated_at: datetime
    con_id: Optional[int] = None
    exchange: str = "SMART"
    currency: str = "USD"
    primary_exchange: Optional[str] = None



@dataclass(frozen=True)
class UniverseSnapshot:
    universe_id: str
    as_of: datetime
    constituents: Mapping[str, TickerUniverseSnapshot]
