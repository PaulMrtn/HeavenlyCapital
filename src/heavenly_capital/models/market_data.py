from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from enum import StrEnum



class AssetType(StrEnum):
    STK = "STK"
    OPT = "OPT"
    CASH = "CASH"


OHLC = namedtuple("OHLC",
                  ["open", "high", "low", "close", "volume", "tick_count", "ts_start", "ts_end"])


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



