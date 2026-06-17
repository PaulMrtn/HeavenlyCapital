from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Optional, Literal, List, Callable
import time
import numpy as np # TODO:LOW - import only what we need
import pickle

class AssetType(StrEnum):
    STK = "STK"
    OPT = "OPT"
    CASH = "CASH"


OHLC = namedtuple("OHLC",
                  ["open", "high", "low", "close", "volume", "tick_count", "ts_start", "ts_end"])


_EXPOSED_FIELDS = {
    "symbol": "contract.symbol",
    "conId": "contract.conId",
    "tradingClass": "contract.tradingClass",
    "last": "last",
    "lastSize": "lastSize",
    "bid": "bid",
    "bidSize": "bidSize",
    "ask": "ask",
    "askSize": "askSize",
    "volume": "volume",
    "close": "close",
    "timestamp": "timestamp",
}


class ReadOnlyTicker:
    __slots__ = ("_ticker", "_callbacks")

    def __init__(self, ticker: Any):
        self._ticker = ticker
        self._callbacks = []

        ticker.updateEvent.connect(self._on_update)

    def __getattr__(self, item):
        path = _EXPOSED_FIELDS.get(item)
        if not path:
            raise AttributeError(f"{item} not exposed")
        obj = self._ticker
        for attr in path.split("."):
            obj = getattr(obj, attr, None)
            if obj is None:
                break
        return obj

    def __getitem__(self, item):
        return self.__getattr__(item)

    def _on_update(self, ticker):
        for cb in tuple(self._callbacks):
            cb(self)

    def subscribe(self, cb):
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def unsubscribe(self, cb):
        self._callbacks.remove(cb)

    def as_dict(self):
        return {k: getattr(self, k) for k in _EXPOSED_FIELDS.keys()}




class TickerManager:

    def __init__(self):
        self.tickers: dict[int, ReadOnlyTicker] = {}
        self._subscriptions: list[Callable[[], None]] = []

        self._refresh_interval = 0.5
        self._last_callback = 0.0

    def add_ticker(self, ticker: Any) -> ReadOnlyTicker:
        conId = ticker.contract.conId

        if conId in self.tickers:
            return self.tickers[conId]

        ro = ReadOnlyTicker(ticker)
        self.tickers[conId] = ro
        ro.subscribe(lambda ro: self._on_ticker_update())

        return ro

    def _on_ticker_update(self):
        now = time.time()
        if now - self._last_callback >= self._refresh_interval:
            for cb in tuple(self._subscriptions):
                cb()
            self._last_callback = time.time()

    def subscribe(self, cb: Callable[[], None]):
        if cb not in self._subscriptions:
            self._subscriptions.append(cb)

    def unsubscribe(self, cb: Callable[[], None]):
        if cb in self._subscriptions:
            self._subscriptions.remove(cb)

    def get_ticker(self, conId: int) -> Optional["ReadOnlyTicker"]:
        ticker = self.tickers.get(conId)
        if ticker is None:
            raise ValueError(
                "Ticker not found. Please check if IBKR Gateway is correctly connected, "
                "ensure market data feed is active, try restarting IBKR Gateway, "
                "and reconnect."
            )
        return ticker

    def all_tickers(self):
        return list(self.tickers.values())




@dataclass(frozen=True, slots=True)
class CandleEvent:
    conId: int
    kind: str
    freq: str
    ohlc: OHLC
    emitted_at: float
    context: dict[str, Any] | None = None #



Kind = Literal["last", "bid", "ask"]
Fields = Literal["open", "high", "low", "close", "volume", "tick_count"]


@dataclass(frozen=True, slots=True)
class BankShape:
    freq: str
    lookback: int
    n_assets: int


class MarketDataBank:
    def __init__(self, *, freq: str, conIds: list[int], lookback: int, dtype: Any = np.float64) -> None:
        if lookback <= 0:
            raise ValueError("MarketDataBank: lookback must be > 0")
        if not conIds:
            raise ValueError("MarketDataBank: conIds must be non-empty")

        self.freq = str(freq)
        self.lookback = int(lookback)

        self.conIds = [int(c) for c in conIds]
        self.conid_to_col: dict[int, int] = {c: i for i, c in enumerate(self.conIds)}
        self.n_assets = len(self.conIds)

        self._ts_end = np.zeros((self.lookback,), dtype=np.float64)
        self._row_head: int = 0
        self._full: bool = False
        self._current_ts_end: Optional[float] = None

        self._kinds: tuple[str, ...] = ("last", "bid", "ask")
        self._fields: tuple[str, ...] = ("open", "high", "low", "close", "volume", "tick_count")

        self._row_fill_count = {kind : np.zeros((self.lookback,), dtype=np.int32) for kind in self._kinds }

        self._data: dict[str, dict[str, np.ndarray]] = {
            col: {kind: np.zeros((self.lookback, self.n_assets), dtype=dtype) for kind in self._kinds}
            for col in self._fields
        }


    @property
    def shape(self) -> BankShape:
        return BankShape(freq=self.freq, lookback=self.lookback, n_assets=self.n_assets)

    @property
    def size(self) -> int:
        return self.lookback if self._full else self._row_head

    def _next_row(self, ts_end: float, event: CandleEvent) -> None:
        self._current_ts_end = float(ts_end)
        self._ts_end[self._row_head] = float(ts_end)

        # Reset row values to NaN
        for fields in self._fields:
            for kind in self._kinds:
                self._data[fields][kind][self._row_head, :] = np.nan

        # Reset row count
        self._row_fill_count[event.kind][self._row_head] = 0

        # Update row head
        self._row_head = (self._row_head + 1) % self.lookback
        if self._row_head == 0:
            self._full = True

    def _logical_view_1d(self, arr: np.ndarray) -> np.ndarray:
        if not self._full:
            return arr[: self._row_head]
        return np.concatenate((arr[self._row_head :], arr[: self._row_head]), axis=0)

    def _logical_view_2d(self, mat: np.ndarray) -> np.ndarray:
        if not self._full:
            return mat[: self._row_head, :]
        return np.vstack((mat[self._row_head :, :], mat[: self._row_head, :]))

    def update(self, event: CandleEvent) -> Optional[bool]:
        if str(event.freq) != self.freq:
            return
        kind = str(event.kind)
        if kind not in self._kinds:
            return
        col = self.conid_to_col.get(int(event.conId))
        if col is None:
            return


        ts_end = float(event.ohlc.ts_end)
        if self._current_ts_end is not None and ts_end < self._current_ts_end:
            return
        if self._current_ts_end is None or ts_end > self._current_ts_end:
            self._next_row(ts_end, event)


        r = (self._row_head - 1) % self.lookback  # current logical row index in the ring
        o = event.ohlc
        # overwrite the matrix cell
        self._data["open"][kind][r, col] = float(o.open)
        self._data["high"][kind][r, col] = float(o.high)
        self._data["low"][kind][r, col] = float(o.low)
        self._data["close"][kind][r, col] = float(o.close)
        self._data["volume"][kind][r, col] = float(o.volume)
        self._data["tick_count"][kind][r, col] = float(o.tick_count)

        self._row_fill_count[event.kind][r] += 1
        updated = (self._row_fill_count[event.kind][r] == self.n_assets)
        return updated

    def ts_end(self) -> np.ndarray:
        return self._logical_view_1d(self._ts_end)

    def matrix(self, *, fields: Fields, kind: Kind) -> np.ndarray:
        return self._logical_view_2d(self._data[str(fields)][str(kind)])

    def slice(self, *, fields: Fields, kind: Kind, conIds: list[int]) -> np.ndarray:
        cols = [self.conid_to_col[int(c)] for c in conIds if int(c) in self.conid_to_col]
        return self.matrix(fields=fields, kind=kind)[:, cols]

    def series(self, *, fields: Fields, kind: Kind, conId: int) -> np.ndarray:
        col = self.conid_to_col[int(conId)]
        return self.matrix(fields=fields, kind=kind)[:, col]

    def tail_matrix(self, *, fields: Fields, kind: Kind, n: int) -> np.ndarray:
        m = self.matrix(fields=fields, kind=kind)
        return m[-int(n) :, :] if n is not None else m

    def tail_series(self, *, fields: Fields, kind: Kind, conId: int, n: int) -> np.ndarray:
        s = self.series(fields=fields, kind=kind, conId=conId)
        return s[-int(n) :] if n is not None else s