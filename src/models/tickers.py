
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class AssetType(StrEnum):
    STOCK = "STOCK"
    OPTION = "OPTION"
    FOREX = "FOREX"



@dataclass(frozen=True)
class TickerUniverseSnapshot:
    internal_code: str
    symbol: str
    asset_type: AssetType
    tickers: list[str]
    updated_at: datetime


@dataclass(frozen=True)
class UniverseSnapshot:
    universe_id: str
    as_of: datetime
    constituents: Mapping[str, TickerUniverseSnapshot]
