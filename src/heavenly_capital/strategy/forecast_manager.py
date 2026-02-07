from __future__ import annotations

from threading import Thread
from typing import Optional, Any, TYPE_CHECKING

from heavenly_capital.core.runtime_config import ForecastConfig, RuntimeModule

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.strategy.feature_manager import FeatureStore




class ModelRegistry:
    ...

class ModelStore:
    ...


class ForecastManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self.feature_store: Optional["FeatureStore"] = None
        self._registry: Optional["ModelRegistry"] = None
        self._store: Optional["ModelStore"] = None

        self._in_worker = Thread(target=self._run, daemon=True)

        self._config: Optional[ForecastConfig] = None
        self._ports: Optional["SystemPorts"] = None

    def configure(self, *, config: ForecastConfig, ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self._registry = ModelRegistry()
        self._store = ModelStore()

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

    def wire_feature_store(self, store: "FeatureStore") -> None:
        self.feature_store = store

    def on_feature_snapshot(self):
        snapshot = self.feature_store.get_latest_snapshot()
        print(snapshot)

    def _run(self) -> None: ...


# ---------------------------------------------



_instance: Optional[ForecastManager] = None

def get_forecast_manager() -> ForecastManager:
    global _instance
    if _instance is None:
        _instance = ForecastManager()
    return _instance