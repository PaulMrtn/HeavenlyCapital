from __future__ import annotations


from dataclasses import dataclass
from typing import runtime_checkable, Protocol, Any


#TODO : load les config depuis un ficher json ( session only )

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
class ThreadConfig:
    critical: int = 2
    standard: int = 4
    bulk: int = 2
    audit: int = 1


@dataclass(frozen=True, slots=True)
class TradingSessionConfig:
    name: str
    account_id: str
    strategy_id: str
    mode: str
    payload: dict[str, Any]



@dataclass(frozen=True, slots=True)
class SessionConfig:
    sessions: tuple[TradingSessionConfig, ...] = (
        TradingSessionConfig(
            name="live_account_0_strategy_0",
            account_id="account_0",
            strategy_id="strategy_0",
            mode="LIVE",
            payload={},
        ),
        TradingSessionConfig(
            name="paper_account_0_strategy_0",
            account_id="account_0",
            strategy_id="strategy_0",
            mode="PAPER",
            payload={},
        ),
    )



@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    ibkr: IBKRConfig = IBKRConfig()
    live_hub: LiveHubConfig = LiveHubConfig()
    historic: HistoricHubConfig = HistoricHubConfig()
    forecast: ForecastConfig = ForecastConfig()
    thread: ThreadConfig = ThreadConfig()
    session_manager: SessionConfig = SessionConfig()



_runtime_config: RuntimeConfig | None = None

def get_global_runtime_config() -> RuntimeConfig:
    # TODO : update runtime_config keys name
    global _runtime_config
    if _runtime_config is None:
        _runtime_config = RuntimeConfig(
            ibkr=IBKRConfig(),
            historic=HistoricHubConfig(),
            live_hub=LiveHubConfig(),
            forecast=ForecastConfig(),
            thread=ThreadConfig(),
            session_manager=SessionConfig(),
        )
    return _runtime_config



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

