from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class IBKRConfig:
    pass

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
    pass


@dataclass(slots=True)
class RuntimeConfig:
    ibkr: IBKRConfig = field(default_factory=IBKRConfig)
    live_hub: LiveHubConfig = field(default_factory=LiveHubConfig)
    historic_hub: HistoricHubConfig = field(default_factory=HistoricHubConfig)
    feature: FeatureConfig = field(default_factory=FeatureConfig)
    forecast: ForecastConfig = field(default_factory=ForecastConfig)
    thread: ThreadConfig = field(default_factory=ThreadConfig)
    session_manager: SessionConfig = field(default_factory=SessionConfig)
