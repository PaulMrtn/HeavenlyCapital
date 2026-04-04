from dataclasses import field, dataclass
from datetime import datetime, timezone
from enum import StrEnum, IntEnum
from typing import Protocol, Any, Optional, Union

from heavenly_capital.models.runtime import RuntimeModule

from heavenly_capital.trading.session_manager import get_session_manager, SessionManager
from heavenly_capital.data.historic import get_historic_data_hub, HistoricDataHub
from heavenly_capital.data.live import get_live_data_hub, LiveDataHub
from heavenly_capital.ibkr.gateway import get_ibkr_gateway, IBKRGateway
from heavenly_capital.strategy.feature_engine import get_feature_manager, FeatureEngine
from heavenly_capital.strategy.forecast_engine import get_forecast_manager, ForecastManager


class SystemStatus(StrEnum):
    BOOTING = "BOOTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


@dataclass
class SystemState:
    status: SystemStatus = SystemStatus.BOOTING
    since: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    detail: str = ""

    def set_status(self, status: "SystemStatus", detail: str = "") -> None:
        if self.status == status:
            return

        self.status = status
        self.since = datetime.now(timezone.utc)
        self.detail = detail


class ExitCode(IntEnum):
    OK = 0
    STRATEGIC_SETUP_COMPLETED = 10
    MARKET_SETUP_COMPLETED = 20
    MARKET_CLOSED_TODAY = 30
    ERROR = 40


class ShutdownScenario(StrEnum):
    BOOTSTRAP_MARKET_CLOSED = "BOOTSTRAP_MARKET_CLOSED"
    MARKET_SETUP_DONE = "MARKET_SETUP_DONE"
    STRATEGIC_SETUP_DONE = "STRATEGIC_SETUP_DONE"
    PROCEDURE_FAILED = "PROCEDURE_FAILED"


@dataclass(frozen=True, slots=True)
class ShutdownRequest:
    scenario: ShutdownScenario
    code: ExitCode
    detail: str = ""



class BootDecision(StrEnum):
    BOOT = "BOOT"
    REBOOT = "REBOOT"
    RECOVERY = "RECOVERY"


@dataclass(slots=True)
class BootPlan:
    decision: BootDecision
    procedure: str  #  ex: "PRE_MARKET", "STRATEGIC_SETUP", "RECOVERY:<phase>"


class MarketPorts(Protocol):
    market_clock: Any
    market_calendar: Any


@dataclass(frozen=True, slots=True)
class DatabasePorts:
    reader: Any
    writer: Any


class ObservabilityPorts(Protocol):
    log_service: Any
    metric_service: Any
    error_service: Any
    notification_service: Any


# Optionnel: une vue "complète" si certains modules ont vraiment besoin de tout
class FullSystemPorts(MarketPorts, DatabasePorts, ObservabilityPorts):
    pass

@dataclass(frozen=True, slots=True)
class SystemPorts:
    market_clock: Any
    market_calendar: Any

    db_service: DatabasePorts

    log_service: Any
    metric_service: Any
    error_service: Any
    notification_service: Any


@dataclass
class RuntimeRegistry:
    ibkr_gateway: Optional[Union["RuntimeModule", "IBKRGateway"]] = None
    historic_hub: Optional[Union["RuntimeModule", "HistoricDataHub"]] = None
    live_hub: Optional[Union["RuntimeModule", "LiveDataHub"]] = None
    feature_manager: Optional[Union["RuntimeModule", "FeatureEngine"]] = None
    forecast_manager: Optional[Union["RuntimeModule", "ForecastManager"]] = None
    session_manager: Optional[Union["RuntimeModule", "SessionManager"]] = None

    @classmethod
    def build(cls) -> "RuntimeRegistry":
        return cls(
            ibkr_gateway=get_ibkr_gateway(),
            historic_hub=get_historic_data_hub(),
            live_hub=get_live_data_hub(),
            feature_manager=get_feature_manager(),
            forecast_manager=get_forecast_manager(),
            session_manager=get_session_manager(),
        )


