from __future__ import annotations

import queue
import random
import threading
import time
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional, Any, Callable, TYPE_CHECKING, Dict

from heavenly_capital.core.runtime_config import IBKRConfig, RuntimeModule
from heavenly_capital.models.market_data import TickEvent

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts



@dataclass
class IbkrContractSpec:
    symbol: str
    sec_type: str
    exchange: str
    currency: str
    primary_exchange: Optional[str] = None
    con_id: Optional[int] = None
    req_id: Optional[int] = None


# region IB Mock

# ---- IB-like enums -------------------------------------------------

class TickType(IntEnum):
    BID_SIZE = 0
    BID = 1
    ASK = 2
    ASK_SIZE = 3
    LAST = 4
    LAST_SIZE = 5
    VOLUME = 6




# ---- EWrapper mock -------------------------------------------------

@dataclass
class TickPrice:
    reqId: int
    tickType: TickType
    price: float

@dataclass
class TickSize:
    reqId: int
    tickType: TickType
    size: int


class MockEWrapper:
    def tickPrice(self, reqId, tickType, price) -> TickPrice:
        return TickPrice(reqId=reqId, tickType=tickType, price=price)

    def tickSize(self, reqId, tickType, size) -> TickSize:
        return TickSize(reqId=reqId, tickType=tickType, size=size)

# ---- EClient mock --------------------------------------------------

class MockEClient:
    def __init__(self, wrapper, interval_ms=250):
        self.wrapper = wrapper
        self.interval = interval_ms / 1000.0
        self._streams = {}
        self._lock = threading.Lock()

    def reqMktData(self, reqId, contract, genericTickList, snapshot, regulatorySnapshot, mktDataOptions):
        if snapshot:
            raise ValueError("Snapshot not supported in this mock")

        price = random.uniform(50, 300)
        high = price
        low = price

        while True:
            delta = random.uniform(-0.1, 0.1)
            price = round(max(0.01, price + delta), 2)
            size = random.randint(1, 500)

            high = round(max(high, price), 2)
            low = round(min(low, price), 2)

            # LAST
            yield self.wrapper.tickPrice(reqId, TickType.LAST, price)
            yield self.wrapper.tickSize(reqId, TickType.LAST_SIZE, size)

            # BID / ASK
            bid = round(price - random.uniform(0.01, 0.03), 2)
            ask = round(price + random.uniform(0.01, 0.03), 2)
            yield self.wrapper.tickPrice(reqId, TickType.BID, bid)
            yield self.wrapper.tickSize(reqId, TickType.BID_SIZE, random.randint(100, 1000))
            yield self.wrapper.tickPrice(reqId, TickType.ASK, ask)
            yield self.wrapper.tickSize(reqId, TickType.ASK_SIZE, random.randint(100, 1000))

            time.sleep(self.interval)

    def cancelMktData(self, reqId):
        with self._lock:
            stop_event = self._streams.pop(reqId, None)
            if stop_event:
                stop_event.set()


# -------------------------------------------------------------------

# endregion


class ReqIdRegistry:
    def __init__(self):
        self.next_req_id = 1
        self.asset_id_by_req_id = {}

    def import_universe(self, contracts: dict[str, Any]) -> None:
        for asset_id, contract in contracts.items():
            req_id = self._acquire_req_id()
            contract.req_id = req_id
            self.asset_id_by_req_id[req_id] = asset_id

    def _acquire_req_id(self):
        req_id = self.next_req_id
        self.next_req_id += 1
        return req_id



class IBKRGateway(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional[IBKRConfig] = None
        self._ports: Optional["SystemPorts"] = None


        self._req_registry = ReqIdRegistry()
        self._contracts: Optional[dict[str, IbkrContractSpec]] = None
        self.asset_id_by_req_id: Dict[int, str] = {}

        # TODO : MOCK sent order (update with OrderObject)
        self._mock_sent_orders: list[dict[str, Any]] = list()
        self._tick_sink: Optional[Callable[[TickEvent], None]] = None

    def configure(self, *, config: IBKRConfig, ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("IBKRGateway: start() called before configure()")
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
    def config(self) -> IBKRConfig:
        if self._config is None:
            raise RuntimeError("IBKRGateway: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("IBKRGateway: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

    # --- MOCK SINK API -------------------------------------------------

    def order_sink(self, session_key, order: dict[str, Any]) -> None:
        # TODO: créer un objet Order contenant toutes les infos de TradingSessionKey et supprimer session-key en input.
        # Appliquer symétriquement la modification
        if not self._configured or not self._started:
            raise RuntimeError("IBKRGateway: order_sink() called while not started/configured")

        self._mock_sent_orders.append(order)

    def get_order_sink(self) -> Callable[[dict[str, Any]], None]:
        return self.order_sink

    def wire_tick_sink(self, sink):
        self._tick_sink = sink

    @property
    def ingest_tick(self) -> Callable[[TickEvent], None]:
        return self._tick_sink

    # ------------------------------------------------------------------

    def fetch_universe_snapshot(self):
        return self._ports.data_access.get_universe_snapshot()

    def assign_req_ids(self, contracts: dict):
        self._req_registry.import_universe(contracts=contracts)
        self.asset_id_by_req_id = self._req_registry.asset_id_by_req_id

    def load_universe_snapshot(self) -> None:
        snapshot = self.fetch_universe_snapshot()
        self._contracts = self._build_ibkr_contract_specs(snapshot)

        self.assign_req_ids(self._contracts)


    @property
    def contracts(self) -> dict[str, IbkrContractSpec] :
        return self._contracts


    @staticmethod
    def _build_ibkr_contract_specs(snapshot: Any) -> dict[str, IbkrContractSpec]:

        contracts = {}
        for asset_id, t in snapshot.constituents.items():
            contracts[asset_id] = IbkrContractSpec(
                symbol=t.symbol,
                sec_type="STK",
                exchange=getattr(t, "exchange", "SMART") or "SMART",
                currency=getattr(t, "currency", "USD") or "USD",
                primary_exchange=getattr(t, "primary_exchange", None),
                con_id=getattr(t, "con_id", None),
                req_id=getattr(t, "req_id", None),
            )

        return contracts

    def on_tick_event(self, tick):
        tick = TickEvent(
            req_id=getattr(tick, 'reqId', None),
            tick_type=getattr(tick, 'tickType', None),
            price=getattr(tick, 'price', None),
            size=getattr(tick, 'size', None),
            ts_gateway=datetime.now()
        )
        self.ingest_tick(tick)

    def start_market_data_stream(self) -> None: ...







_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance




