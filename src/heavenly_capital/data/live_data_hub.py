from __future__ import annotations

from typing import Optional, Any, TYPE_CHECKING, Callable, Dict, cast

from ib_async import Contract, Ticker

from heavenly_capital.core.runtime_config import LiveHubConfig, RuntimeModule
from heavenly_capital.data.bus import EventBus
from heavenly_capital.data.db_mock import TradingSessionDB
from heavenly_capital.models.market_data import OHLC, TickerManager

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.ibkr.gateway import Contract


tsDB = TradingSessionDB()

class OHLCAggregator:
    def __init__(self):
        self.prices: list[float] = []
        self.volumes: list[float] = []
        self.timestamps: list[float] = []

    def add(self, price: float, size: float, ts: float):
        self.prices.append(price)
        self.volumes.append(size)
        self.timestamps.append(ts)

    def flush(self, ts_start: float, ts_end: float) -> "OHLC":
        p_snapshot, self.prices = self.prices, []
        v_snapshot, self.volumes = self.volumes, []
        t_snapshot, self.timestamps = self.timestamps, []

        if not p_snapshot:
            return OHLC(
                open=0.0, high=0.0, low=0.0, close=0.0,
                volume=0.0, tick_count=0,
                ts_start=ts_start, ts_end=ts_end
            )

        return OHLC(
            open=p_snapshot[0],
            high=max(p_snapshot),
            low=min(p_snapshot),
            close=p_snapshot[-1],
            volume=sum(v_snapshot),
            tick_count=len(p_snapshot),
            ts_start=ts_start,
            ts_end=ts_end
        )


class InstrumentPipeline:
    def __init__(self, contract: "Contract"):
        self.contract = contract
        self.conId = contract.conId

        self.last_agg = OHLCAggregator()
        self.bid_agg = OHLCAggregator()
        self.ask_agg = OHLCAggregator()

    def on_ticker(self, tick: "Ticker"):
        ts = tick.timestamp

        last = tick.last
        if last > 0:
            self.last_agg.add(last, tick.lastSize, ts)

        bid = tick.bid
        if bid > 0:
            self.bid_agg.add(bid, tick.bidSize, ts)

        ask = tick.ask
        if ask > 0:
            self.ask_agg.add(ask, tick.askSize, ts)

    def aggregate_all(self, ts_start: float, ts_end: float) -> dict[str, Optional["OHLC"]]:
        return {
            "last": self.last_agg.flush(ts_start, ts_end),
            "bid": self.bid_agg.flush(ts_start, ts_end),
            "ask": self.ask_agg.flush(ts_start, ts_end)
        }


class LiveDataHub(RuntimeModule):

    def __init__(self) -> None:
        self._last_update_interval = None
        self._configured: bool = False
        self._started: bool = False

        self._last_agg_time: Optional[float] = None

        self._pipelines: Dict[int, "InstrumentPipeline"] = {}
        self._tickers = TickerManager()
        self.candle_bus = EventBus(name="CandleBus")


        self._config: Optional["LiveHubConfig"] = None
        self._ports: Optional["SystemPorts"] = None


    def configure(self, *, config: "LiveHubConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("LiveDataHub: start() called before configure()")

        self._started = True

    def stop(self) -> None:
        #TODO:MEDIUM handle worker and sweeper with stop fn
        self._started = False


    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> LiveHubConfig:
        if self._config is None:
            raise RuntimeError("LiveDataHub: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("LiveDataHub: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {"is_healthy": True}

    def initialize_pipelines(self, contracts: dict[str, Contract]):
        self._pipelines = {
            c.conId: InstrumentPipeline(c) for c in contracts.values()
        }

    def ingest_ticker(self, ticker: Ticker):
        conId = ticker.contract.conId

        if conId not in self._tickers.tickers:
            self._tickers.add_ticker(ticker)

        pipeline = self._pipelines.get(ticker.contract.conId)
        if pipeline is not None:
            pipeline.on_ticker(ticker)

    @property
    def ingest_port(self) -> Callable:
        return self.ingest_ticker

    @property
    def tickers(self) -> "TickerManager":
        return self._tickers

    def aggregate_and_publish_candles(self, current_time: float):
        if self._last_agg_time is None:
            self._last_agg_time = current_time
            return

        if current_time - self._last_agg_time >= 5:
            ts_end = current_time - (current_time % 5)
            ts_start = ts_end - 5

            for conId, pipeline in self._pipelines.items():
                bars = pipeline.aggregate_all(ts_start, ts_end)
                self.candle_bus.publish(conId, bars)

            self._last_agg_time = current_time




_instance: Optional[LiveDataHub] = None

def get_live_data_hub() -> LiveDataHub:
    global _instance
    if _instance is None:
        _instance = LiveDataHub()
    return _instance




