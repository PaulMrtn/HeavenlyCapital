from dataclasses import field, dataclass
from datetime import datetime, timezone
from enum import StrEnum, IntEnum
from typing import Protocol, Any, Optional, Union

from heavenly_capital.models.runtime import RuntimeModule
from heavenly_capital.models.session import MarketDaySession

from heavenly_capital.trading.session_manager import get_session_manager, SessionManager
from heavenly_capital.core.thread import get_thread_manager, ThreadManager
from heavenly_capital.data.historic import get_historic_data_hub, HistoricDataHub
from heavenly_capital.data.live import get_live_data_hub, LiveDataHub
from heavenly_capital.ibkr.gateway import get_ibkr_gateway, IBKRGateway
from heavenly_capital.strategy.feature_manager import get_feature_manager, FeatureManager
from heavenly_capital.strategy.forecast_manager import get_forecast_manager, ForecastManager


class SystemStatus(StrEnum):
    BOOTING = "BOOTING"
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class SystemState:
    status: SystemStatus = SystemStatus.STOPPED
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
    MARKET_CLOSED_TODAY = 20


class ShutdownScenario(StrEnum):
    BOOTSTRAP_MARKET_CLOSED = "BOOTSTRAP_MARKET_CLOSED"
    SESSION_END_NORMAL = "SESSION_END_NORMAL"
    FATAL_ERROR = "FATAL_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ShutdownRequest:
    scenario: ShutdownScenario
    code: ExitCode
    detail: str = ""



class BootDecision(StrEnum):
    BOOT_NEW_SESSION = "BOOT_NEW_SESSION"
    START_TRADING_SESSION = "START_TRADING_SESSION"
    REBOOT = "REBOOT"
    RECOVERY = "RECOVERY"


@dataclass(slots=True)
class BootPlan:
    decision: BootDecision
    session: MarketDaySession
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
    thread_manager: Optional[Union["RuntimeModule", "ThreadManager"]] = None
    ibkr_gateway: Optional[Union["RuntimeModule", "IBKRGateway"]] = None
    historic_hub: Optional[Union["RuntimeModule", "HistoricDataHub"]] = None
    live_hub: Optional[Union["RuntimeModule", "LiveDataHub"]] = None
    feature_manager: Optional[Union["RuntimeModule", "FeatureManager"]] = None
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
            thread_manager=get_thread_manager(),
            session_manager=get_session_manager(),
        )
