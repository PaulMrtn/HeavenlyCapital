from __future__ import annotations


from dataclasses import dataclass
from typing import Protocol, Any

from src.core.system_manager import SystemPorts


@dataclass(frozen=True, slots=True)
class IBKRConfig:
    host: str = "127.0.0.1"
    port: int = 4002
    client_id: int = 1


@dataclass(frozen=True, slots=True)
class LiveHubConfig:
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class HistoricHubConfig:
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ForecastConfig:
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    ibkr: IBKRConfig = IBKRConfig()
    live_hub: LiveHubConfig = LiveHubConfig()
    historic: HistoricHubConfig = HistoricHubConfig()
    forecast: ForecastConfig = ForecastConfig()


class ConfigurableModule(Protocol):
    def configure(self, *, config: Any, ports: "SystemPorts") -> None: ...


class Startable(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


