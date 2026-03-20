from __future__ import annotations

from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import runtime_checkable, Protocol, Any, Optional

from heavenly_capital.data.db_mock import TradingSessionDB
from heavenly_capital.models.session import TradingSessionConfig

#TODO : load les config depuis un ficher json ( session only )

# @dataclass(frozen=True, slots=True)
# class IBKRSessionConfig:
#     session_name: str
#     host: str
#     port: int
#     account_type: str        # "LIVE" ou "PAPER"
#     permission_level: str    # "MASTER" ou "STANDARD"
#     enable: bool = True
#
# @dataclass(frozen=True, slots=True)
# class IBKRConfig:
#     sessions: list[SessionConfig]



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
class FeatureConfig:
    pass


@dataclass(frozen=True, slots=True)
class ThreadConfig:
    pass






@dataclass(frozen=True, slots=True)
class SessionConfig:
    sessions: tuple[TradingSessionConfig, ...]


def load_session_config(db: "TradingSessionDB") -> SessionConfig:
    rows = db.fetch_all()
    sessions = [TradingSessionConfig.from_database(row, db) for row in rows]
    return SessionConfig(sessions=tuple(sessions))



@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    ibkr: IBKRConfig
    live_hub: LiveHubConfig
    historic_hub: HistoricHubConfig
    feature: FeatureConfig
    forecast: ForecastConfig
    thread: ThreadConfig
    session_manager: SessionConfig

def build_runtime_config(db: TradingSessionDB) -> RuntimeConfig:
    return RuntimeConfig(
        ibkr=IBKRConfig(),
        live_hub=LiveHubConfig(),
        historic_hub=HistoricHubConfig(),
        feature=FeatureConfig(),
        forecast=ForecastConfig(),
        thread=ThreadConfig(),
        session_manager=load_session_config(db),
    )

_runtime_config: RuntimeConfig | None = None

def get_global_runtime_config(db: TradingSessionDB) -> RuntimeConfig:
    global _runtime_config

    if _runtime_config is None:
        _runtime_config = build_runtime_config(db)
    return _runtime_config




# TODO:LOW - Handle this dumb heritage with async interface

@runtime_checkable
class RuntimeModule(Protocol):

    def configure(self, *, config: Any, ports: Any) -> Any: ...

    def start(self) -> Any: ...

    def stop(self) -> Any: ...

    @property
    def is_configured(self) -> bool: ...

    @property
    def is_started(self) -> bool: ...

    def health_check(self) -> dict[str, Any]: ...



class AsyncRuntimeModule(RuntimeModule):

    @abstractmethod
    async def start(self) -> Any:
        pass

    @abstractmethod
    async def stop(self) -> Any:
        pass




class ModuleType(str, Enum):
    ORDERS = "orders"
    PORTFOLIO = "portfolio"
    RISK = "risk"


class ModuleRouter(ABC):
    @abstractmethod
    def transfer(
        self,
        *,
        source: ModuleType,
        target: ModuleType,
        payload: Any,
    ) -> None:
        ...



class BaseModule(ABC):

    def __init__(self) -> None:
        self._router: Optional[ModuleRouter] = None
        self._module_type: Optional[ModuleType] = None

    def bind_router(self, router: ModuleRouter, module_type: ModuleType) -> None:
        self._router = router
        self._module_type = module_type

    def send(self, target: ModuleType, payload: Any) -> None:
        self._router.transfer(
            source=self._module_type,
            target=target,
            payload=payload,
        )

    def _receive(self, source: ModuleType, payload: Any) -> None:
        pass