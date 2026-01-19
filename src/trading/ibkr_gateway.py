from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Any, Callable, TYPE_CHECKING, Dict

from src.core.runtime_config import IBKRConfig, RuntimeModule
from src.models.market_data import MarketTick, MarketDataInstrument
from src.models.tickers import UniverseSnapshot

if TYPE_CHECKING:
    from src.core.system_manager import SystemPorts


TickCallback = Callable[[MarketTick], None]


# --- MOCK Subscriber API -------------------------------------------------
class MockMarketDataSubscriber:

    def __init__(self, *, interval_s: float = 0.5, seed: int = 123) -> None:
        self._interval_s = interval_s
        self._rng = random.Random(seed)

        self._lock = threading.Lock()
        self._callbacks: Dict[str, TickCallback] = {}
        self._meta: Dict[str, MarketDataInstrument] = {}
        self._last_price: Dict[str, float] = {}

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, name="mock-md-subscriber", daemon=True)
        self._thread.start()

    def stop(self, *, timeout_s: float = 2.0) -> None:
        self._stop_evt.set()
        t = self._thread
        if t:
            t.join(timeout=timeout_s)

    def subscribe(self, instrument: MarketDataInstrument, callback: TickCallback) -> str:
        handle = f"sub_{instrument.symbol}"  # handle stable, sans info sensible
        with self._lock:
            self._callbacks[handle] = callback
            self._meta[handle] = instrument
            self._last_price.setdefault(handle, 100.0 + self._rng.random() * 10.0)
        return handle

    def unsubscribe(self, handle: str) -> None:
        with self._lock:
            self._callbacks.pop(handle, None)
            self._meta.pop(handle, None)
            self._last_price.pop(handle, None)

    def _run(self) -> None:
        while not self._stop_evt.is_set():
            now = datetime.now(timezone.utc)
            with self._lock:
                items = list(self._callbacks.items())

            for handle, cb in items:
                tick = self._make_tick(handle, now)
                try:
                    cb(tick)
                except Exception:
                    # en mock, on évite de tuer le thread; à toi de logger si besoin
                    pass

            time.sleep(self._interval_s)

    def _make_tick(self, handle: str, now: datetime) -> MarketTick:
        with self._lock:
            instrument = self._meta[handle]
            base = self._last_price[handle]

        delta = self._rng.normalvariate(0.0, 0.05)
        last = max(0.01, base + delta)
        spread = max(0.01, abs(self._rng.normalvariate(0.02, 0.01)))
        bid = last - spread / 2
        ask = last + spread / 2

        with self._lock:
            self._last_price[handle] = last

        return MarketTick(
            symbol=instrument.symbol,
            ts=now,
            last=last,
            bid=bid,
            ask=ask,
        )


    # ------------------------------------------------------------------

class IBKRGateway(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional[IBKRConfig] = None
        self._ports: Optional["SystemPorts"] = None

        self._universe_snapshot: Optional[UniverseSnapshot] = None

        # TODO : MOCK sent order (update with OrderObject)
        self._mock_sent_orders: list[dict[str, Any]] = list()

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
        # Appliquer sysmetriquement la modificatin
        if not self._configured or not self._started:
            raise RuntimeError("IBKRGateway: order_sink() called while not started/configured")

        self._mock_sent_orders.append(order)

    def get_order_sink(self) -> Callable[[dict[str, Any]], None]:
        return self.order_sink

    # ------------------------------------------------------------------


    def refresh_universe_snapshot(self) -> None:
        self._universe_snapshot = self._ports.data_access.get_universe_snapshot()
        # MarketDataComponents = self.load_components_from_snapshot()

    def subscribe_universe_market_data(self) -> None: ...





_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance