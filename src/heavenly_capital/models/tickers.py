from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from heavenly_capital.models.market_data import AssetType


@dataclass(frozen=True)
class TickerUniverseSnapshot:
    symbol: str
    asset_type: AssetType
    name: str
    sector: str
    con_id: Optional[int] = None
    exchange: str = "SMART"
    currency: str = "USD"
    primary_exchange: Optional[str] = None


@dataclass(frozen=True)
class UniverseSnapshot:
    universe_id: str
    constituents: Mapping[int, TickerUniverseSnapshot]
