from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace, field
from itertools import product
from queue import Queue
from threading import Thread
from typing import Optional, Dict, Any, TYPE_CHECKING, Tuple, Generator
from ib_async import Contract
import numpy as np

from heavenly_capital.core.runtime_config import FeatureConfig, RuntimeModule, FeatureSpec
from heavenly_capital.data.bus import EventBus
from heavenly_capital.models.market_data import CandleEvent, MarketDataBank
from heavenly_capital.strategy.features import FEATURE_REGISTRY, FeatureCache

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts



@dataclass
class FeatureVector:
    data: np.ndarray
    feature_names: tuple[str, ...]
    freq: str
    scope: str
    updated_at: float
    conId: int | None = None
    _name_to_idx: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self):
        self._name_to_idx = {n: i for i, n in enumerate(self.feature_names)}
    def get_value(self, name: str) -> float:
        idx = self._name_to_idx.get(name)
        return float(self.data[idx]) if idx is not None else np.nan
    def to_numpy(self):
        return self.data



class FeatureRegistry:
    def __init__(self, specs: tuple[FeatureSpec, ...]):
        self._specs = self._expand_specs(specs)
        self._build_index()

    @staticmethod
    def _expand_specs(specs: tuple[FeatureSpec, ...]) -> list[FeatureSpec]:
        expanded: list[FeatureSpec] = []

        for s in specs:
            freqs = s.freq if isinstance(s.freq, list) else [s.freq]
            kinds = s.kind if isinstance(s.kind, list) else [s.kind]

            for f, k in product(freqs, kinds):
                unique_name = f"{s.id}_{s.fields}_{k}_{f}"

                new_spec = replace(
                    s,
                    name=unique_name,
                    freq=f,
                    kind=k
                )
                expanded.append(new_spec)

        return expanded

    def _build_index(self):
        by_sfk: dict[tuple[str, str, str], list[FeatureSpec]] = defaultdict(list)

        for spec in self._specs:
            key = (spec.scope, str(spec.freq), str(spec.kind))
            by_sfk[key].append(spec)

        for key in by_sfk:
            by_sfk[key].sort(key=lambda s: s.order)

        self._specs_by_sfk = dict(by_sfk)
        self._feature_names_by_sfk = {
            k: tuple(s.name for s in v)
            for k, v in by_sfk.items()
        }
        self._n_features_by_sfk = {
            k: len(v)
            for k, v in by_sfk.items()
        }

    def get_specs(self, *, scope: str, freq: str, kind: str) -> list[FeatureSpec]:
        return self._specs_by_sfk.get((scope, str(freq), str(kind)), [])

    def get_feature_names(self, *, scope: str, freq: str, kind: str) -> tuple[str, ...]:
        return self._feature_names_by_sfk.get((scope, str(freq), str(kind)), ())

    def get_n_features(self, *, scope: str, freq: str, kind: str) -> int:
        return self._n_features_by_sfk.get((scope, str(freq), str(kind)), 0)



@dataclass(frozen=True)
class CacheKey:
    freq: str
    scope: str
    conId: int | None
    feature_name: str


class FeatureStore:
    #TODO: HIGHEST Revoir cette class (swap buffer etc)
    def __init__(self):
        self.store: dict[CacheKey, float] = {}
        self._ts_index: dict[int, list[CacheKey]] = defaultdict(list)

    def commit(self, fv: FeatureVector):
        ts_bucket = int(fv.updated_at)

        for i, name in enumerate(fv.feature_names):
            key = CacheKey(
                freq=fv.freq,
                scope=fv.scope,
                conId=fv.conId,
                feature_name=name,
            )
            self.store[key] = fv.data[i]
            self._ts_index[ts_bucket].append(key)

    def get_latest_snapshot(self) -> dict[CacheKey, float]:
        if not self._ts_index:
            return {}

        last_ts = max(self._ts_index.keys())
        keys = self._ts_index[last_ts]

        return {k: self.store[k] for k in keys}



class FeatureNotifier:
    def __init__(self):
        self._listeners = []

    def register(self, listener):
        self._listeners.append(listener)

    def notify_snapshot_ready(self):
        for listener in self._listeners:
            listener()




class FeatureManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._conids: list[int] = []
        self._banks: dict[str, "MarketDataBank"] = {}
        self._last_seen: Dict[Tuple[int, str, str], float] = {}

        self._registry: Optional["FeatureRegistry"] = None
        self.store: Optional["FeatureStore"] = None
        self.notifier: Optional["FeatureNotifier"] = None

        self._in_queue = Queue()
        self._in_bus: Optional["EventBus"] = None
        self._in_token: Optional[int] = None
        self._in_worker = Thread(target=self._process_candle_event, daemon=True)

        self._config: Optional["FeatureConfig"] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: "FeatureConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self._registry = FeatureRegistry(specs=config.specs)
        self.store: FeatureStore = FeatureStore()
        self.notifier: FeatureNotifier = FeatureNotifier()

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

    def _update_bank(self, event: "CandleEvent") -> bool | None:
        bank = self._banks.get(str(event.freq))
        if bank is None:
            return None
        return bank.update(event)

    def _build_vector(self, event: "CandleEvent", scope: str) -> Optional["FeatureVector"]:
        bank = self._banks.get(str(event.freq))
        cache = FeatureCache(bank, event, scope)

        specs = self._registry.get_specs(scope=scope, freq=event.freq, kind=event.kind)
        if not specs:
            return None
        names = self._registry.get_feature_names(scope=scope, freq=event.freq, kind=event.kind)

        buffer = np.zeros(len(specs), dtype=np.float64)

        for i, spec in enumerate(specs):
            plugin_fn = FEATURE_REGISTRY.get(spec.plugin)
            if not plugin_fn:
                feature_value = np.nan
            else:
                feature_value = plugin_fn(spec=spec, cache=cache)

            buffer[i] = feature_value
            if spec.cache:
                cache.store_feature(spec.name, feature_value)

        return FeatureVector(
            data=buffer,
            feature_names=names,
            conId=event.conId if scope == "per_asset" else None,
            freq=event.freq,
            scope=scope,
            updated_at=float(event.ohlc.ts_end)
        )

    def event_to_features(self, event) -> list[Any]:
        updated = self._update_bank(event)

        vectors = []
        fv = self._build_vector(event, scope="per_asset")
        if fv:
            vectors.append(fv)

        if updated:
            fv = self._build_vector(event, scope="cross_asset")
            if fv:
                vectors.append(fv)

        return vectors

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

                for vector in self.event_to_features(event):
                    self.store.commit(vector)

            finally:
                self._in_queue.task_done()

            #TODO:HIGH Make test to be sure this condition is enough
            if self._in_queue.qsize() == 0 :
                self.notifier.notify_snapshot_ready()


_instance: Optional["FeatureManager"] = None

def get_feature_manager() -> "FeatureManager":
    global _instance
    if _instance is None:
        _instance = FeatureManager()
    return _instance