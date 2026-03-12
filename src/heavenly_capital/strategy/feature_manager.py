from __future__ import annotations

import queue
from collections import defaultdict, deque
from dataclasses import dataclass, replace, field
from itertools import product
from queue import Queue
from typing import Optional, Dict, Any, TYPE_CHECKING, Tuple
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



@dataclass(slots=True)
class FeatureSnapshot:
    by_conid: Dict[int, Dict[str, float]]

    def get(self, conid: int, feature_names: list[str]) -> Dict[str, float]:
        data = self.by_conid.get(conid, {})
        return {name: data[name] for name in feature_names}


class FeatureStore:
    def __init__(self, history_size: int = 20):
        self._latest: Dict[int, Dict[str, float]] = defaultdict(dict)
        self._history: Dict[int, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=history_size))
        )

    def commit(self, fv: FeatureVector) -> None:
        conId = fv.conId
        ts = fv.updated_at

        for name, value in zip(fv.feature_names, fv.data):
            self._latest[conId][name] = value
            self._history[conId][name].append((ts, value))

    def build_snapshot(self) -> FeatureSnapshot:
        return FeatureSnapshot(by_conid=dict(self._latest))


    # ------ API -----------------------

    def get_history(self, conId: int, name: str) -> list[tuple[float, float]]:
        return list(self._history.get(conId, {}).get(name, []))

    def get_feature_map(self, name: str) -> dict[int, float]:
        result = {}
        for conId, feats in self._latest.items():
            if name in feats:
                result[conId] = feats[name]
        return result

    def get_latest(self, conId: int, name: str) -> float | None:
        return self._latest.get(conId, {}).get(name)


    # -----------------------------------


class FeatureManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._conids: list[int] = []
        self._banks: dict[str, "MarketDataBank"] = {}
        self._last_seen: Dict[Tuple[int, str, str], float] = {}
        self._pending_snapshot = False

        self._registry: Optional["FeatureRegistry"] = None
        self.store: Optional["FeatureStore"] = None

        self._in_queue = Queue()
        self._in_bus: Optional["EventBus"] = None
        self._in_token: Optional[int] = None

        self.out_queue = Queue() # TODO:HIGH - Add Bus Event

        self._config: Optional["FeatureConfig"] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: "FeatureConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self._registry = FeatureRegistry(specs=config.specs)
        self.store: FeatureStore = FeatureStore()

        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("FeatureManager: start() called before configure()")

        self._started = True

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
            conid = getattr(c, "conId") or 0
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

    def _event_to_features(self, event) -> list[Any]:
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



# ------------------- WARNING --------------
#     def _build_fusion_vectors(self, freq: str) -> list[FeatureVector]:
#         vectors: list[FeatureVector] = []
# 
#         specs = self._registry.get_specs(scope="derived", freq=freq, kind="last")
#         for spec in specs:
#             plugin_fn = FEATURE_REGISTRY.get(spec.plugin)
#             if plugin_fn is None:
#                 continue
# 
#             result = plugin_fn(spec=spec, store=self.store, freq=freq)
#             for conId, value in result.items():
#                 fv = FeatureVector(
#                     data=np.array([value]),
#                     feature_names=[spec.name],
#                     conId=conId,
#                     freq=freq,
#                     scope="derived",
#                     updated_at=time.time()
#                 )
#                 vectors.append(fv)
# 
#         return vectors

    # -------------------------------------------
    


    def process_candle_events(self) -> None:
        processed = False

        while True:
            try:
                event = self._in_queue.get_nowait()

            except queue.Empty:
                break

            if not self._started:
                self._in_queue.task_done()
                continue

            if not self._bool_process_event(event):
                self._in_queue.task_done()
                continue

            for vector in self._event_to_features(event):
                self.store.commit(vector)

            # for vector in self._build_fusion_vectors(event.freq):
            #     self.store.commit(vector)

            processed = True
            self._in_queue.task_done()

        if processed or self._pending_snapshot:
            snapshot = self.store.build_snapshot()
            self.out_queue.put(snapshot)
            self._pending_snapshot = False





_instance: Optional["FeatureManager"] = None

def get_feature_manager() -> "FeatureManager":
    global _instance
    if _instance is None:
        _instance = FeatureManager()
    return _instance