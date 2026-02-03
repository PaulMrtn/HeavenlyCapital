from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import runtime_checkable, Protocol, Any, Optional, Literal


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
class FeatureSpec:
    """
    - name: stable identifier (key in the store)
    - plugin: plugin identifier (e.g. "sma", "corr", "spread")
    - params: hyperparameters (window size, asset pairs, method, etc.)
    """
    name: str
    plugin: str
    freq: str | list[str]
    kind: str | list[str]
    scope: Literal["per_asset", "cross_asset"]
    fields: str = "close"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    maxlen_by_freq: dict[str, Optional[int]] = field(
        default_factory=lambda: {
        "5s": 10,
        "30s": 10,
        "1m": 10,
        "5m": 10,
        "10m": 10,
        "30m": 10,
        "1h": 10,
    })

    specs: tuple[FeatureSpec, ...] = (
        FeatureSpec(
            name="return_1__close__last__5s",
            plugin="return_1",
            freq="1m",
            kind="last",
            scope="per_asset"
        ),
    )


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
    historic_hub: HistoricHubConfig = HistoricHubConfig()
    feature: FeatureConfig = FeatureConfig()
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
            historic_hub=HistoricHubConfig(),
            live_hub=LiveHubConfig(),
            feature=FeatureConfig(),
            forecast=ForecastConfig(),
            thread=ThreadConfig(),
            session_manager=SessionConfig(),
        )
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