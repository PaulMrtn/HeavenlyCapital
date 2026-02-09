from __future__ import annotations

from pathlib import Path
from queue import Queue
from time import time

import joblib
from threading import Thread
from typing import Optional, Any, TYPE_CHECKING
from ib_async import Contract

from heavenly_capital.core.runtime_config import ForecastConfig, RuntimeModule, ModelSpec
from heavenly_capital.strategy.artifacts import DecisionRecord, ModelOutput, ModelState

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.strategy.feature_manager import FeatureStore



class ModelRegistry:
    def __init__(self, specs: tuple[ModelSpec, ...]) -> None:
        self._specs: list[ModelSpec] = list(specs)
        self._by_id: dict[str, ModelSpec] = {
            spec.model_id: spec for spec in specs
        }

    def get(self, model_id: str) -> ModelSpec:
        return self._by_id[model_id]

    def all(self) -> list[ModelSpec]:
        return list(self._specs)



class ModelStore:
    def __init__(self, registry: ModelRegistry, conids: list[int]) -> None:
        self._records: dict[str, dict[int, list["DecisionRecord"]]] = {
            spec.model_id: {conid: [] for conid in conids} for spec in registry.all()
        }

    def record(
        self,
        *,
        model_id: str,
        conid: int,
        record: DecisionRecord,
    ) -> None:

        if model_id not in self._records:
            raise ValueError(f"Unknown model_id: {model_id}")
        if conid not in self._records[model_id]:
            raise ValueError(f"Instrument {conid} not in initial universe")

        self._records[model_id][conid].append(record)

    def get_by_model(self, model_id: str) -> dict[int, list["DecisionRecord"]]:
        return self._records[model_id]

    def get_all(self) -> dict[str, dict[int, list["DecisionRecord"]]]:
        return self._records



class ForecastModel:
    def __init__(self, spec: "ModelSpec"):
        self.spec = spec
        self._model = None

    def load(self) -> None:
        if self._model is None:
            self._model = self._load_model(self.spec.path)

    @staticmethod
    def _load_model(path: Path):
        return joblib.load(path)

    def predict(self, features: dict[str, float]) -> float:
        if self._model is None:
            raise RuntimeError(f"Model {self.spec.model_id} not loaded")
        return self._model.predict([features])[0]




class ModelPool:
    def __init__(self, registry: "ModelRegistry") -> None:
        self._models: dict[str, ForecastModel] = {
            spec.model_id: ForecastModel(spec)
            for spec in registry.all()
        }

    def get(self, model_id: str) -> "ForecastModel":
        return self._models[model_id]

    def all(self) -> list["ForecastModel"]:
        return list(self._models.values())




class ForecastManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._conids: list[int] = []

        self._registry: Optional["ModelRegistry"] = None
        self._store: Optional["ModelStore"] = None
        self._states: dict[tuple[str, int], "ModelState"] = None
        self._pool: Optional["ModelPool"] = None

        self._in_queue = Queue(maxsize=1)
        self._in_worker = Thread(target=self._run, daemon=True)

        self._config: Optional[ForecastConfig] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: "ForecastConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self._registry = ModelRegistry(specs=config.specs)
        self._store = ModelStore(registry=self._registry, conids=self._conids)
        self._pool = ModelPool(registry=self._registry)

        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("FeatureManager: start() called before configure()")

        self._started = True
        if not self._in_worker.is_alive():
            self._in_worker.start()

    def stop(self) -> None:
        self._started = False

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> ForecastConfig:
        if self._config is None:
            raise RuntimeError("ForecastManager: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("ForecastManager: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

    # ---- API ------------------------------------

    def initialize_universe(self, contracts: dict[str, "Contract"]) -> None:
        conids: list[int] = []
        for c in contracts.values():
            conid = getattr(c, "conId") or 0
            if conid > 0:
                conids.append(int(conid))

        self._conids = sorted(set(conids))

    def wire_feature_store(self, queue: Queue) -> None:
        self._in_queue = queue

    def load_pretrained_models(self) -> None:
        if self._pool is None:
            raise RuntimeError("ModelPool not initialized")

        for model in self._pool.all():
            model.load()

    def _build_record(self, *, output: "ModelOutput", model_id, conid) -> DecisionRecord:
        return DecisionRecord(
            model_id=model_id,
            conid=conid,
            timestamp=output.timestamp,
            step=output.step,
            decision=output.decision,
            forced=output.forced,
            score=output.score,
            penalty=output.penalty,
            output_at=time(),
        )


    def _run(self) -> None:

        while True:
            features = self._in_queue.get()
            if features is None:
                break

            for model_id, model in self._models.items():
                for conid in self._conids:
                    key = (model_id, conid)
                    state = self._states.get(key)

                    output, new_state = model.predict(features, state)
                    self._states[key] = new_state

                    record = self._build_record(output=output, model_id=model_id, conid=conid)
                    self._store.record(record=record, model_id=model_id, conid=conid)


# ---------------------------------------------



_instance: Optional[ForecastManager] = None

def get_forecast_manager() -> ForecastManager:
    global _instance
    if _instance is None:
        _instance = ForecastManager()
    return _instance