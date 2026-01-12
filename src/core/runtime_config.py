from __future__ import annotations


from dataclasses import dataclass
from typing import Protocol, Any, runtime_checkable


@dataclass(frozen=True, slots=True)
class IBKRConfig:
    host: str = "127.0.0.1"
    port: int = 4002
    client_id: int = 1


@dataclass(frozen=True, slots=True)
class LiveHubConfig:
    pass


@dataclass(frozen=True, slots=True)
class HistoricHubConfig:
    pass


@dataclass(frozen=True, slots=True)
class ForecastConfig:
    pass

@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    ibkr: IBKRConfig = IBKRConfig()
    live_hub: LiveHubConfig = LiveHubConfig()
    historic: HistoricHubConfig = HistoricHubConfig()
    forecast: ForecastConfig = ForecastConfig()


_runtime_config: RuntimeConfig | None = None

def get_global_runtime_config() -> RuntimeConfig:
    global _runtime_config
    if _runtime_config is None:
        _runtime_config = RuntimeConfig(
            ibkr=IBKRConfig(),
            historic=HistoricHubConfig(),
            live_hub=LiveHubConfig(),
            forecast=ForecastConfig(),
        )
    return _runtime_config



# TODO : RuntimeModule ne semble pas a sa place

@runtime_checkable
class RuntimeModule(Protocol):
    def configure(self, *, config: Any, ports: Any) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...

    @property
    def is_configured(self) -> bool: ...

    @property
    def is_started(self) -> bool: ...

    def health_check(self) -> dict[str, Any]: ...





