from __future__ import annotations

from pathlib import Path
from queue import Queue, Empty
import joblib
from typing import Any, TYPE_CHECKING
from ib_async import Contract

from typing import List, Dict, Optional

from heavenly_capital.core.runtime_config import ForecastConfig, RuntimeModule
from heavenly_capital.strategy.artifacts import DecisionRecord, ModelOutput, ModelSpec, ModelState
from heavenly_capital.data.db_mock import TradingSessionDB


if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts


tsDB = TradingSessionDB()


class ModelRegistry:

    def __init__(self, specs: list[ModelSpec]) -> None:
        self._specs: list[ModelSpec] = specs
        self._by_id: dict[str, ModelSpec] = {
            spec.model_id: spec for spec in specs
        }

    def get(self, model_id: str) -> ModelSpec:
        return self._by_id[model_id]

    def all(self) -> list[ModelSpec]:
        return self._specs



class ModelStore:
    def __init__(self, trading_day: str | None = None) -> None:
        self._records: dict[str, dict[int, list[DecisionRecord]]] = {}
        self.trading_day: str | None = trading_day

    def initialize_records(self, registry: "ModelRegistry", conids: List[int]) -> None:
        self._records = {spec.model_id: {conid: [] for conid in conids} for spec in registry.all()}

    def record(self, model_id: str, conid: int, record: "DecisionRecord") -> None:
        if model_id not in self._records:
            raise ValueError(f"Unknown model_id: {model_id}")
        if conid not in self._records[model_id]:
            raise ValueError(f"Instrument {conid} not in initial universe")

        self._records[model_id][conid].append(record)

    def get_by_model(self, model_id: str) -> Dict[int, list["DecisionRecord"]]:
        return self._records[model_id]

    def flush(self):
        for model_id, con_dict in self._records.items():
            for conid in con_dict:
                con_dict[conid].clear()

    def to_payload(self) -> list[dict]:
        return [
            {
                "model_name": model_id,
                "version": getattr(r, "version", 1.0),
                "con_id": conid,
                "step": r.step,
                "decision": r.decision,
                "score": getattr(r, "score", None),  # <-- ajouter ici
                "output_at": r.output_at,
                "prediction_ts": r.timestamp,
                "trading_day": self.trading_day
            }
            for model_id, con_dict in self._records.items()
            for conid, rec_list in con_dict.items()
            for r in rec_list
        ]


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
        self._prediction_plan: list[tuple[ForecastModel, int]] = []
        self._routing_registry: dict[tuple[int, str], list[str]] = {}
        self._in_queue = Queue(maxsize=1)

        self.bus_out = EventBus(name="ForecastBus")

        self._registry: Optional["ModelRegistry"] = None
        self._store: Optional["ModelStore"] = None
        self._states: dict[tuple[str, int], Optional[ModelState]] = {}
        self._pool: Optional["ModelPool"] = None

        self._config: Optional["ForecastConfig"] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: "ForecastConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self._registry = self.load_model_registry()
        self._pool = ModelPool(registry=self._registry)
        self._store = ModelStore(trading_day=self._ports.market_calendar.today())

        self._states = {
            (spec.model_id, conid): None
            for spec in self._registry.all()
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
    def config(self) -> "ForecastConfig":
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

    @staticmethod
    def load_model_registry() -> "ModelRegistry":
        rows = tsDB.get_forecast_models_configs()
        specs = [ModelSpec.from_snapshot(r) for r in rows]
        return ModelRegistry(specs)

    def get_positions_and_targets(self) -> list[dict]:
        today = self._ports.market_calendar.today()
        return tsDB.fetch_positions_and_targets(today)

    def build_prediction_and_routing(self) -> None:
        positions = self.get_positions_and_targets()

        grouped_positions = self._group_positions_by_session(positions)

        models_by_type = self._group_models_by_type()

        self._prediction_plan, self._routing_registry = self._build_plan_and_routing(grouped_positions, models_by_type)

    def _group_positions_by_session(self, positions: list[dict]) -> dict[str, list[dict]]:
        grouped = {"LIVE": [], "PAPER": [], "OTHER": []}
        all_con_ids = {p["con_id"] for p in positions}

        for pos in positions:
            session = pos.get("session_mode", "OTHER")
            if session in grouped:
                grouped[session].append(pos)
            else:
                grouped["OTHER"].append(pos)

        unknown_con_ids = set(self._conids) - all_con_ids
        for con_id in unknown_con_ids:
            grouped["OTHER"].append({"con_id": con_id, "portfolio_id": None})

        return grouped

    def _group_models_by_type(self) -> dict[str, list[ModelSpec]]:
        model_types_order = ["STOP_LOSS", "SELL", "BUY"]
        grouped = {mt: [] for mt in model_types_order}
        for m in self._registry.all():
            grouped[m.model_type.name].append(m)
        return grouped

    def _build_plan_and_routing(
            self,
            grouped_positions: dict[str, list[dict]],
            models_by_type: dict[str, list[ModelSpec]]
    ) -> tuple[list[tuple[ForecastModel, int]], dict[tuple[int, str], list[str]]]:

        prediction_plan: list[tuple[ForecastModel, int]] = []
        routing_registry: dict[tuple[int, str], list[str]] = {}

        seen_con_model: set[tuple[str, int]] = set()

        session_order = ["LIVE", "PAPER", "OTHER"]
        model_order = ["STOP_LOSS", "SELL", "BUY"]

        for session in session_order:
            for pos in grouped_positions.get(session, []):
                con_id = pos["con_id"]
                portfolio_id = pos.get("portfolio_id")

                for mt in model_order:
                    key_routing = (con_id, mt)
                    if key_routing not in routing_registry:
                        routing_registry[key_routing] = []

                    if portfolio_id and portfolio_id not in routing_registry[key_routing]:
                        routing_registry[key_routing].append(portfolio_id)

                    for model in models_by_type.get(mt, []):
                        key_model = (model.model_id, con_id)
                        if key_model not in seen_con_model:
                            prediction_plan.append((self._pool.get(model.model_id), con_id))
                            seen_con_model.add(key_model)

        return prediction_plan, routing_registry


    def setup_models_and_store(self) -> None:
        if self._pool is None:
            raise RuntimeError("ModelPool not initialized")

        self._pool.load()
        self._store.initialize_records(self._registry, self._conids)
        self.build_prediction_and_routing()


    def _route_prediction(self, conid: int, model_type: str, output: ModelOutput) -> None:
        portfolio_id = self._routing_registry.get((conid, model_type))

        if portfolio_id is None:
            return

        for ptf_id in portfolio_ids:
            self.bus_out.publish(entity_id=ptf_id, data={"conid": conid, "signal": output})


    def _make_prediction(self, model_id, model, conid, snapshot):
        key = (model_id, conid)
        state = self._states.get(key)
        features = snapshot.get(conid, model.input_names)

        output, new_state = model.predict(features, state)
        self._states[key] = new_state

        self._route_prediction(conid, model.spec.model_type.name, output)

        record = DecisionRecord.from_model_output(
            model_id=model_id,
            conid=conid,
            output=output,
        )
        self._store.record(record=record, model_id=model_id, conid=conid)

    def persist_predictions(self) -> None:
        payload = self._store.to_payload()
        tsDB.persist_model_records(payload)
        self._store.flush()


    def run_predictions(self) -> None:
        try:
            feature_snapshot = self._in_queue.get_nowait()
        except Empty:
            return

        if feature_snapshot is None:
            return

        for model, conid in self._prediction_plan:
            self._make_prediction(
                model_id=model.spec.model_id,
                model=model,
                conid=conid,
                snapshot=feature_snapshot
            )

        self.persist_predictions()

        print(self.bus_out)
        print(self.bus_out._subscribers)
        print(self.bus_out._subscribers_all)
        print(self.bus_out._subscriptions)

        breakpoint()




_instance: Optional[ForecastManager] = None

def get_forecast_manager() -> ForecastManager:
    global _instance
    if _instance is None:
        _instance = ForecastManager()
    return _instance