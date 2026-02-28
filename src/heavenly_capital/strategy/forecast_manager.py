from __future__ import annotations

from pathlib import Path
from queue import Queue, Empty
import joblib
from typing import Optional, Any, TYPE_CHECKING, List, Dict
from ib_async import Contract

from heavenly_capital.core.runtime_config import ForecastConfig, RuntimeModule, ModelSpec
from heavenly_capital.strategy.artifacts import DecisionRecord, ModelOutput, ModelState

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts



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
    def __init__(self) -> None:
        self._records = {}

    def initialize_records(self, registry: "ModelRegistry", conids: List[int]) -> None:
        self._records = {spec.model_id: {conid: [] for conid in conids} for spec in registry.all()}

    def record(
        self,
        *,
        model_id: str,
        conid: int,
        record: "DecisionRecord",
    ) -> None:

        if model_id not in self._records:
            raise ValueError(f"Unknown model_id: {model_id}")
        if conid not in self._records[model_id]:
            raise ValueError(f"Instrument {conid} not in initial universe")

        self._records[model_id][conid].append(record)

    def get_by_model(self, model_id: str) -> Dict[int, list["DecisionRecord"]]:
        return self._records[model_id]

    def get_all(self) -> Dict[str, Dict[int, list["DecisionRecord"]]]:
        return self._records



class ForecastModel:
    def __init__(self, spec: "ModelSpec"):
        self.spec = spec
        self._model = None

    def load(self) -> None:
        if self._model is None:
            self._model = self._load_model(self.spec.path)

    @property
    def input_names(self) -> List[str]:
        return self._model._input_names

    @staticmethod
    def _load_model(path: Path):
        return joblib.load(path)

    def predict(
        self,
        features: dict[str, float],
        state: Optional[ModelState] = None
    ) -> tuple[ModelOutput, ModelState]:
        if self._model is None:
            raise RuntimeError(f"Model {self.spec.model_id} not loaded")
        return self._model.predict(features, state)



class ModelPool:
    def __init__(self, registry: "ModelRegistry") -> None:
        self._models: dict[str, ForecastModel] = {
            spec.model_id: ForecastModel(spec)
            for spec in registry.all()
        }

    @property
    def items(self):
        return self._models.items()

    def get(self, model_id: str) -> "ForecastModel":
        return self._models[model_id]

    def all(self) -> list["ForecastModel"]:
        return list(self._models.values())

    def load(self) -> None:
        for model in self.all():
            model.load()



class ForecastManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._conids: list[int] = []

        self._registry: Optional["ModelRegistry"] = None
        self._store: Optional["ModelStore"] = None
        self._states: dict[tuple[str, int], Optional[ModelState]] = {}
        self._pool: Optional["ModelPool"] = None

        self._in_queue = Queue(maxsize=1)

        self._config: Optional[ForecastConfig] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: "ForecastConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self._registry = ModelRegistry(specs=config.specs)
        self._pool = ModelPool(registry=self._registry)
        self._store = ModelStore()

        self._states = {
            (spec.model_id, conid): None
            for spec in config.specs
            for conid in self._conids
        }

        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("FeatureManager: start() called before configure()")

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

    def initialize_universe(self, contracts: dict[str, "Contract"]) -> None:
        conids: list[int] = []
        for c in contracts.values():
            conid = getattr(c, "conId") or 0
            if conid > 0:
                conids.append(int(conid))

        self._conids = sorted(set(conids))

    def wire_feature_store(self, queue: Queue) -> None:
        self._in_queue = queue

    def setup_models_and_store(self) -> None:
        if self._pool is None:
            raise RuntimeError("ModelPool not initialized")

        self._pool.load()
        self._store.initialize_records(self._registry, self._conids)


    def _make_prediction(self, model_id, model, conid, snapshot):
        key = (model_id, conid)
        state = self._states.get(key)

        features = snapshot.get(conid, model.input_names)

        output, new_state = model.predict(features, state)
        self._states[key] = new_state

        record = DecisionRecord.from_model_output(
            model_id=model_id,
            conid=conid,
            output=output,
        )

        self._store.record(
            record=record,
            model_id=model_id,
            conid=conid
        )


    def run_predictions(self) -> None:
        try:
            feature = self._in_queue.get_nowait()
        except Empty:
            return

        if feature is None:
            return

        for model_id, model in self._pool.items:
            for conid in self._conids:
                self._make_prediction(
                    model_id=model_id,
                    model=model,
                    conid=conid,
                    snapshot=feature
                )



_instance: Optional[ForecastManager] = None

def get_forecast_manager() -> ForecastManager:
    global _instance
    if _instance is None:
        _instance = ForecastManager()
    return _instance