from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import Optional, Any, Callable, TYPE_CHECKING, Dict

from heavenly_capital.core.runtime_config import IBKRConfig, RuntimeModule
from heavenly_capital.models.market_data import MarketTick, MarketDataInstrument


if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts


TickCallback = Callable[[MarketTick], None]


@dataclass(frozen=True)
class IbkrContractSpec:
    symbol: str
    sec_type: str
    exchange: str
    currency: str
    primary_exchange: Optional[str] = None
    con_id: Optional[int] = None
    md_req_id: Optional[int] = None



# --- MOCK Subscriber API -------------------------------------------------
class MockMarketDataSubscriber:
    """
    Mock de market data pour tests/démo.

    Modes supportés :
    1) Streaming (historique du comportement) :
       - start() lance un thread qui émet périodiquement des ticks via callbacks.
       - subscribe()/unsubscribe() gèrent les abonnements.

    2) Snapshots (nouveau / pour polling régulier) :
       - get_snapshot(contract) renvoie un MarketTick "one-shot".
       - get_snapshots(contracts_by_asset_id) renvoie un dict de ticks.

    Notes :
    - Le prix "last" est la référence, et évolue légèrement entre deux appels.
    - bid/ask sont remplis seulement si ces champs existent dans MarketTick.
    """

    def __init__(
        self,
        *,
        interval_s: float = 0.5,
        seed: int = 123,
        initial_price: float = 100.0,
        step_std: float = 0.10,
        spread_mean: float = 0.02,
        spread_std: float = 0.01,
    ) -> None:
        self._interval_s = interval_s
        self._rng = random.Random(seed)

        self._initial_price = float(initial_price)
        self._step_std = float(step_std)
        self._spread_mean = float(spread_mean)
        self._spread_std = float(spread_std)

        self._lock = threading.Lock()
        self._callbacks: Dict[str, TickCallback] = {}
        self._specs: Dict[str, IbkrContractSpec] = {}
        self._last_price: Dict[str, float] = {}

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._tick_field_names = {f.name for f in fields(MarketTick)}

    # -----------------------
    # Streaming API (existant)
    # -----------------------
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

    def subscribe(self, contract: IbkrContractSpec, callback: TickCallback) -> str:
        handle = self._make_handle(contract)
        with self._lock:
            self._callbacks[handle] = callback
            self._specs[handle] = contract
            self._last_price.setdefault(handle, self._initial_price + self._rng.random() * 10.0)
        return handle

    def unsubscribe(self, handle: str) -> None:
        with self._lock:
            self._callbacks.pop(handle, None)
            self._specs.pop(handle, None)
            self._last_price.pop(handle, None)

    # -----------------------
    # Snapshot API (nouveau)
    # -----------------------
    def get_snapshot(self, contract: IbkrContractSpec, *, as_of: Optional[datetime] = None) -> MarketTick:
        """
        Renvoie un tick snapshot pour un contrat (sans abonnement).
        """
        ts = as_of or datetime.now(timezone.utc)
        handle = self._make_handle(contract)

        with self._lock:
            self._specs.setdefault(handle, contract)
            self._last_price.setdefault(handle, self._initial_price + self._rng.random() * 10.0)

        return self._make_tick(handle, ts)

    def get_snapshots(
        self,
        contracts_by_asset_id: Dict[str, IbkrContractSpec],
        *,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, MarketTick]:
        """
        Batch snapshot : idéal pour un polling régulier (toutes les X secondes).
        La clé est un asset_id interne (stable côté appli).
        """
        ts = as_of or datetime.now(timezone.utc)
        out: Dict[str, MarketTick] = {}
        for asset_id, contract in contracts_by_asset_id.items():
            out[asset_id] = self.get_snapshot(contract, as_of=ts)
        return out

    # -----------------------
    # Internals
    # -----------------------
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
                    # Mock : on ignore les erreurs de callback pour ne pas arrêter le thread
                    pass

            time.sleep(self._interval_s)

    def _make_tick(self, handle: str, ts: datetime) -> MarketTick:
        with self._lock:
            contract = self._specs.get(handle)
            last_prev = self._last_price.get(handle)

        if contract is None:
            # Handle inconnu : tick minimal "safe"
            payload: Dict[str, Any] = {"ts": ts, "symbol": "UNKNOWN", "last": float("nan")}
            return MarketTick(**payload)

        if last_prev is None:
            last_prev = self._initial_price + self._rng.random() * 10.0

        # Évolution (marche aléatoire)
        last = max(0.01, last_prev + self._rng.normalvariate(0.0, self._step_std))

        with self._lock:
            self._last_price[handle] = last

        payload: Dict[str, Any] = {
            "ts": ts,
            "symbol": getattr(contract, "symbol", "UNKNOWN"),
            "last": last,
        }

        # bid/ask si supportés par MarketTick
        if "bid" in self._tick_field_names or "ask" in self._tick_field_names:
            spread = max(0.01, self._rng.normalvariate(self._spread_mean, self._spread_std))
            if "bid" in self._tick_field_names:
                payload["bid"] = last - spread / 2
            if "ask" in self._tick_field_names:
                payload["ask"] = last + spread / 2

        # Champs additionnels optionnels (uniquement si présents dans MarketTick)
        for name in ("con_id", "exchange", "currency", "sec_type"):
            if name in self._tick_field_names and getattr(contract, name, None) is not None:
                payload[name] = getattr(contract, name)

        return MarketTick(**payload)

    def _make_handle(self, contract: IbkrContractSpec) -> str:
        """
        Identifiant stable pour retrouver l’état du mock (dernier prix).
        Priorité à con_id si présent.
        """
        con_id = getattr(contract, "con_id", None)
        if con_id is not None:
            return f"conid:{con_id}"

        sec_type = getattr(contract, "sec_type", None) or getattr(contract, "asset_type", None) or "UNK"
        symbol = getattr(contract, "symbol", None) or "UNK"
        exchange = getattr(contract, "exchange", None) or "UNK"
        currency = getattr(contract, "currency", None) or "UNK"
        primary = getattr(contract, "primary_exchange", None) or ""
        return f"{sec_type}:{symbol}:{exchange}:{currency}:{primary}".replace(" ", "")


    # ------------------------------------------------------------------

class IBKRGateway(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional[IBKRConfig] = None
        self._ports: Optional["SystemPorts"] = None

        self._contracts: Optional[dict[str, IbkrContractSpec]] = None
        self.asset_id_by_md_req_id: Dict[int, str] = {}

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


    def load_universe_snapshot(self) -> None:
        snapshot = self._ports.data_access.get_universe_snapshot()
        self._contracts = self._build_ibkr_contract_specs(snapshot)



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
            )

        return contracts

    def start_market_data_stream(self) -> None: ...









_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance