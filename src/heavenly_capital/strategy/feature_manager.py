from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from queue import Queue
from threading import Lock, Thread
from typing import Optional, Dict, Any, TYPE_CHECKING, Tuple
from ib_async import Contract

from heavenly_capital.core.runtime_config import FeatureConfig, RuntimeModule, FeatureSpec
from heavenly_capital.data.bus import EventBus
from heavenly_capital.models.market_data import CandleEvent, MarketDataBank
from heavenly_capital.strategy.features import FEATURE_REGISTRY

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts



# region dataclasses
@dataclass(frozen=True, slots=True)
class InstrumentFeatureSnapshot:
    conId: int
    features: Dict[str, float]
    updated_at: float


@dataclass(frozen=True, slots=True)
class CrossFeatureSnapshot:
    """
    Features globales inter-instruments (ex: corrélations).
    """
    features: Dict[str, float]
    updated_at: float


class InstrumentFeatureStore:
    """
    Swap-buffer par instrument: conId -> snapshot immuable.
    """
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshots: Dict[int, InstrumentFeatureSnapshot] = {}

    def get_snapshot(self, conId: int) -> Optional[InstrumentFeatureSnapshot]:
        return self._snapshots.get(conId)

    def set_features(self, *, conId: int, features: Dict[str, float], updated_at: float) -> InstrumentFeatureSnapshot:
        """
        Remplace complètement le set de features d'un instrument.
        """
        snap = InstrumentFeatureSnapshot(conId=conId, features=dict(features), updated_at=float(updated_at))
        with self._lock:
            self._snapshots[conId] = snap
        return snap

    def upsert_features(self, *, conId: int, patch: Dict[str, float], updated_at: float) -> InstrumentFeatureSnapshot:
        """
        Merge partiel: ajoute / remplace uniquement les clés du patch.
        """
        with self._lock:
            prev = self._snapshots.get(conId)
            merged = dict(prev.features) if prev is not None else {}
            merged.update(patch)

            snap = InstrumentFeatureSnapshot(conId=conId, features=merged, updated_at=float(updated_at))
            self._snapshots[conId] = snap
            return snap


class CrossFeatureStore:
    """
    Swap-buffer global: 1 snapshot immuable inter-instruments.
    """
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot: Optional[CrossFeatureSnapshot] = None

    def get_snapshot(self) -> Optional[CrossFeatureSnapshot]:
        return self._snapshot

    def set_features(self, *, features: Dict[str, float], updated_at: float) -> CrossFeatureSnapshot:
        snap = CrossFeatureSnapshot(features=dict(features), updated_at=float(updated_at))
        with self._lock:
            self._snapshot = snap
        return snap

    def upsert_features(self, *, patch: Dict[str, float], updated_at: float) -> CrossFeatureSnapshot:
        with self._lock:
            prev = self._snapshot.features if self._snapshot is not None else {}
            merged = dict(prev)
            merged.update(patch)

            snap = CrossFeatureSnapshot(features=merged, updated_at=float(updated_at))
            self._snapshot = snap
            return snap

# endregion


@dataclass(slots=True)
class EngineResult:
    instrument_patch: dict[str, float]
    cross_patch: dict[str, float]




class FeatureEngine:
    def __init__(self, *, specs: tuple[FeatureSpec, ...]) -> None:
        self._specs = self._expand_specs(specs)

        self._by_route: dict[tuple[str, str], list[FeatureSpec]] = {}
        for s in self._specs:
            self._by_route.setdefault((s.freq, s.kind), []).append(s)

    def _expand_specs(self, specs: tuple[FeatureSpec, ...]) -> list[FeatureSpec]:
        expanded: list[FeatureSpec] = []

        for s in specs:
            freqs = s.freq if isinstance(s.freq, list) else [s.freq]
            kinds = s.kind if isinstance(s.kind, list) else [s.kind]

            for f, k in product(freqs, kinds):
                expanded.append(
                    FeatureSpec(
                        name=s.name,
                        plugin=s.plugin,
                        freq=f,
                        kind=k,
                        scope=s.scope,
                        fields=s.fields,
                        params=s.params,
                    )
                )
        return expanded

    def on_event(
        self,
        *,
        event: CandleEvent,
        banks: dict[str, MarketDataBank],
    ) -> EngineResult:

        bank = banks.get(str(event.freq))
        if bank is None:
            return EngineResult({}, {})

        specs = self._by_route.get((str(event.freq), str(event.kind)), [])
        if not specs:
            return EngineResult({}, {})

        instrument_patch: dict[str, float] = {}
        cross_patch: dict[str, float] = {}

        for spec in specs:
            plugin_fn = FEATURE_REGISTRY.get(spec.plugin)
            if plugin_fn is None:
                continue

            patch = plugin_fn(spec=spec, bank=bank, event=event)
            if not patch:
                continue

            if spec.scope == "cross_asset":
                cross_patch.update(patch)
            else:
                instrument_patch.update(patch)

        return EngineResult(instrument_patch, cross_patch)





class FeatureManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        # temporary
        self.instrument_store = InstrumentFeatureStore()
        self.cross_store = CrossFeatureStore()

        self._engine: Optional[FeatureEngine] = None

        self._conids: list[int] = []
        self._banks: dict[str, "MarketDataBank"] = {}
        self._last_seen: Dict[Tuple[int, str, str], float] = {}

        self._in_queue = Queue()
        self._in_bus: Optional["EventBus"] = None
        self._in_token: Optional[int] = None
        self._in_worker = Thread(target=self._process_candle_event, daemon=True)

        self._config: Optional["FeatureConfig"] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: "FeatureConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self._engine = FeatureEngine(specs=self._config.specs)

        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("FeatureManager: start() called before configure()")

        self._started = True
        if not self._in_worker.is_alive():
            self._in_worker.start()

    def stop(self) -> None:
        self._started = False

        if self._in_token is not None:
            try:
                self._in_queue.put_nowait(None)
                self._in_bus.unsubscribe(self._in_token)
            except Exception:
                pass
            finally:
                self._in_token = None
                self._in_bus = None

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> FeatureConfig:
        if self._config is None:
            raise RuntimeError("FeatureManager: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("FeatureManager: ports not set (configure() not called)")
        return self._ports


    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }


# ---- Beginning of API --------

    def initialize_universe(self, contracts: dict[str, "Contract"]) -> None:
        conids: list[int] = []
        for c in contracts.values():
            conid = getattr(c, "conId", 0) or 0
            if conid > 0:
                conids.append(int(conid))

        self._conids = sorted(set(conids))

    def build_market_data_banks(self) -> None:
        self._banks.clear()

        for freq, lookback in self.config.maxlen_by_freq.items():
            self._banks[str(freq)] = MarketDataBank(
                freq=str(freq),
                conIds=self._conids,
                lookback=int(lookback),
            )

    def wire_historic_candle_bus(self, candle_bus: "EventBus") -> None:
        self._in_bus = candle_bus

    def subscribe_to_live_candle(self) -> None:
        if self._in_token is None and self._in_bus is None:
            raise RuntimeError("FeatureManager: input bus not set (call wire_historic_candle_bus() first)")

        self._in_token =  self._in_bus.subscribe_all(self._on_candle_event)

    def _on_candle_event(self, conId: int, event: "CandleEvent") -> None:
        self._in_queue.put(event)

    def _bool_process_event(self, event: "CandleEvent") -> bool:
        key = (int(event.conId), str(event.kind), str(event.freq))
        last_seen = self._last_seen.get(key)

        if last_seen is not None and event.ohlc.ts_end <= last_seen:
            return False

        self._last_seen[key] = float(event.ohlc.ts_end)
        return True

    def _update_bank(self, event: "CandleEvent") -> None:
        bank = self._banks.get(str(event.freq))
        if bank is None:
            return
        bank.update(event)

    # -----------------------------------------------------------
    def _compute_and_commit(self, event: "CandleEvent") -> None:
        if self._engine is None:
            return

        result = self._engine.on_event(event=event, banks=self._banks)

        if result.instrument_patch:
            self.instrument_store.upsert_features(
                conId=int(event.conId),
                patch=result.instrument_patch,
                updated_at=float(event.ohlc.ts_end),
            )

        if result.cross_patch:
            self.cross_store.upsert_features(
                patch=result.cross_patch,
                updated_at=float(event.ohlc.ts_end),
            )

    # -----------------------------------------------------------

    def _process_candle_event(self) -> None:
        while True:
            event = self._in_queue.get()
            if event is None:
                break

            try:
                if not self._started:
                    continue

                if not self._bool_process_event(event):
                    continue

                self._update_bank(event)

                self._compute_and_commit(event)

            finally:
                self._in_queue.task_done()




_instance: Optional["FeatureManager"] = None

def get_feature_manager() -> "FeatureManager":
    global _instance
    if _instance is None:
        _instance = FeatureManager()
    return _instance