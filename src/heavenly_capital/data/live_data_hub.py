from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from queue import Queue
from threading import Thread

from typing import Optional, Any, TYPE_CHECKING, Callable, Dict

from ib_async import Contract

from heavenly_capital.core.runtime_config import LiveHubConfig, RuntimeModule
from heavenly_capital.models.market_data import TickEvent

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.ibkr.gateway import Contract


# temporary
class TickType(IntEnum):
    BID_SIZE = 0
    BID = 1
    ASK = 2
    ASK_SIZE = 3
    LAST = 4
    LAST_SIZE = 5
    VOLUME = 6


@dataclass
class LastKnownState:
    # TODO:MEDIUM : this object should be replaced by a more efficient data structure
    ticks: Dict["TickType", float] = field(default_factory=dict)
    last_ts_gateway: Optional[datetime] = None


OHLC = namedtuple("OHLC",
                  ["open", "high", "low", "close", "volume", "len_tick", "ts_start", "ts_end"])


class InstrumentPipeline:

    def __init__(self, contract: "Contract") -> None:
        self._contract = contract

        self.tick_buffer = []
        self.state: Optional["LastKnownState"] = LastKnownState()

    def on_tick(self, tick: "TickEvent"):
        if tick.tick_type is not None:
            value = tick.price if tick.price is not None else tick.size
            if value is not None:
                self.state.ticks[tick.tick_type] = value

        self.state.last_ts_gateway = tick.ts_gateway

        if tick.tick_type in (TickType.LAST, TickType.LAST_SIZE):
            self.tick_buffer.append(tick)


    def aggregate_ohlc(self) -> Optional[OHLC]:
        if not self.tick_buffer:
            return None

        buffer = self.tick_buffer
        self.tick_buffer = []

        prices = [t.price for t in buffer if t.price is not None]
        if not prices:
            return None

        # TODO:HIGHEST : Verify the volume calculation
        volume = sum(t.size for t in buffer if t.size is not None)

        ts_start = buffer[0].ts_gateway
        ts_end = buffer[-1].ts_gateway

        return OHLC(
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=volume,
            len_tick=len(prices),
            ts_start=ts_start,
            ts_end=ts_end,
        )



class LiveDataHub(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._pipelines: Dict[int, "InstrumentPipeline"] = {}

        self._queue = Queue()
        self._worker = Thread(target=self._process_ticks, daemon=True)

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
        self._worker.start()


    def stop(self) -> None:
        self._started = False

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        # TODO:MEDIUM : rename is_stared to is_running
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
        return {
            "is_healthy": True,
        }

    def initialize_pipelines(self, contracts: dict[str, Contract]):
        self._pipelines = {
            c.conId: InstrumentPipeline(c) for c in contracts.values()
        }


    def _ingest(self, tick):
        self._queue.put(tick)

    @property
    def ingest_port(self) -> Callable:
        return self._ingest

    def _process_ticks(self):

        while self._started:
            try:
                tick: TickEvent = self._queue.get(timeout=1)

                pipeline = self._pipelines.get(tick.conId)
                if pipeline:
                    print(tick)
                    # pipeline.on_tick(tick)
                self._queue.task_done()

            except Exception:
                continue






_instance: Optional[LiveDataHub] = None

def get_live_data_hub() -> LiveDataHub:
    global _instance
    if _instance is None:
        _instance = LiveDataHub()
    return _instance