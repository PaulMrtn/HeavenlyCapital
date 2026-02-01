from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Optional, Any, TYPE_CHECKING, Tuple, Dict, List, Deque
from ib_async import Contract

from heavenly_capital.core.runtime_config import HistoricHubConfig, RuntimeModule
from heavenly_capital.models.market_data import OHLC

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts




BASE_SEC = 5

_freq_seconds = {
    "30s": 30,
    "1m": 60,
    "5m": 300,
    "10m": 600,
    "30m": 1800,
    "1h": 3600,
}

# region Candle

@dataclass
class CandleResampler:
    target_count: int
    seen_count: int = 0

    has_data: bool = False
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    tick_count: int = 0

    ts_start: float = 0.0
    ts_end: float = 0.0

    @classmethod
    def create(cls, *, target_count: int) -> "CandleResampler":
        return cls(target_count=int(target_count))

    def reset(self) -> None:
        self.seen_count = 0
        self.has_data = False
        self.open = self.high = self.low = self.close = 0.0
        self.volume = 0.0
        self.tick_count = 0
        self.ts_start = 0.0
        self.ts_end = 0.0

    def push(self, bar: "OHLC") -> Optional["OHLC"]:
        if self.seen_count == 0:
            self.ts_start = bar.ts_start
        self.ts_end = bar.ts_end
        self.seen_count += 1

        if bar.tick_count > 0:
            if not self.has_data:
                self.has_data = True
                self.open = bar.open
                self.high = bar.high
                self.low = bar.low
                self.close = bar.close
            else:
                self.high = max(self.high, bar.high)
                self.low = min(self.low, bar.low)
                self.close = bar.close
            self.volume += bar.volume
            self.tick_count += bar.tick_count

        if self.seen_count < self.target_count:
            return None

        out = self._build_candle()
        self.reset()
        return out

    def _build_candle(self) -> "OHLC":
        if not self.has_data:
            return OHLC(
                open=0.0, high=0.0, low=0.0, close=0.0,
                volume=0.0, tick_count=0,
                ts_start=self.ts_start, ts_end=self.ts_end
            )
        return OHLC(
            open=self.open, high=self.high, low=self.low, close=self.close,
            volume=self.volume, tick_count=self.tick_count,
            ts_start=self.ts_start, ts_end=self.ts_end
        )


class ResampleCascade:
    def __init__(self, freq_seconds: Dict[str, int]) -> None:
        self.base_sec = BASE_SEC
        self.levels: List[Tuple[str, CandleResampler]] = []
        ordered = sorted(freq_seconds.items(), key=lambda x: x[1])

        prev_sec = self.base_sec
        for label, sec in ordered:
            count = sec // prev_sec
            self.levels.append((label, CandleResampler.create(target_count=count)))
            prev_sec = sec

    def push_5s(self, bar: "OHLC") -> Dict[str, "OHLC"]:
        outputs: Dict[str, OHLC] = {}
        current_bar = bar
        for label, resampler in self.levels:
            out = resampler.push(current_bar)
            if out is None:
                break
            outputs[label] = out
            current_bar = out
        return outputs


class CandleStore:
    def __init__(self, maxlen_map: Optional[Dict[str, int]] = None) -> None:
        self.maxlen_map = maxlen_map or {}
        self._data: Dict[str, Deque[OHLC]] = {}

    def add(self, freq: str, ohlc: OHLC) -> None:
        if freq not in self._data:
            self._data[freq] = deque(maxlen=self.maxlen_map.get(freq))
        self._data[freq].append(ohlc)

    def get_bars(self, freq: str, n: Optional[int] = None) -> list[OHLC]:
        if n is None:
            return list(self._data[freq])
        return list(self._data[freq])[-int(n):]


class CandleManager:
    def __init__(
        self,
        *,
        maxlen_map: Optional[dict[str, int]] = None,
        kinds: tuple[str, ...] = ("last", "bid", "ask"),
    ):
        self.freq_seconds = _freq_seconds
        self.maxlen_map = maxlen_map or {}
        self.kinds = kinds

        self.stores: Dict[int, Dict[str, CandleStore]] = {}

        self.resamplers: Dict[int, Dict[str, ResampleCascade]] = {}

    def register_conid(self, conId: int) -> None:
        if conId in self.stores:
            return

        self.stores[conId] = {k: CandleStore(maxlen_map=self.maxlen_map) for k in self.kinds}
        self.resamplers[conId] = {k: ResampleCascade(self.freq_seconds) for k in self.kinds}

    def push_5s(self, conId: int, bar5s: Dict[str, OHLC]) -> Dict[str, Dict[str, OHLC]]:
        self.register_conid(conId)

        out_all: Dict[str, Dict[str, OHLC]] = {}

        for kind in self.kinds:
            bar = bar5s.get(kind)
            if bar is None:
                continue

            self.stores[conId][kind].add("5s", bar)

            cascade = self.resamplers[conId][kind]
            new_bars = cascade.push_5s(bar)

            for freq, ohlc in new_bars.items():
                self.stores[conId][kind].add(freq, ohlc)

            if new_bars:
                out_all[kind] = new_bars

        return out_all

    def get_bars(self, conId: int, *, kind: str, freq: str, n: Optional[int] = None) -> list[OHLC]:
        return self.stores[conId][kind].get_bars(freq, n)


# endregion



class HistoricDataHub(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._candle_manager = CandleManager(
            maxlen_map={},
            kinds=("last", "bid", "ask")
            )

        self._contracts = None

        self._config: Optional[HistoricHubConfig] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: HistoricHubConfig, ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("HistoricDataHub: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> HistoricHubConfig:
        if self._config is None:
            raise RuntimeError("HistoricHubConfig: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("HistoricHubConfig: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

    def initialize_universe(self, contracts: dict[str, "Contract"]) -> None: ...




_instance: Optional[HistoricDataHub] = None

def get_historic_data_hub() -> HistoricDataHub:
    global _instance
    if _instance is None:
        _instance = HistoricDataHub()
    return _instance
