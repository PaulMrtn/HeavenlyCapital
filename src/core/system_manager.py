# core/system_manager.py

from __future__ import annotations

import threading
from typing import Optional, Protocol, Iterable
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.market_clock import MarketStateChangeEvent
from src.monitoring.error_service import NullErrorService, ErrorService
from src.monitoring.log_service import LogService, NullLogService
from src.monitoring.metric_service import MetricService, NullMetricService
from src.monitoring.notification_service import NullNotificationService, NotificationService
from src.monitoring.health_checks import ConnectionStatus, ReadinessCheck



class SystemStatus(str, Enum):
    BOOTING = "BOOTING"
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass(slots=True)
class SystemState:
    status: SystemStatus = SystemStatus.STOPPED
    since: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    detail: str = ""


class ExitCode(IntEnum):
    OK = 0
    MARKET_CLOSED_TODAY = 20

class ShutdownScenario(str, Enum):
    BOOTSTRAP_MARKET_CLOSED = "BOOTSTRAP_MARKET_CLOSED"
    SESSION_END_NORMAL = "SESSION_END_NORMAL"
    FATAL_ERROR = "FATAL_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ShutdownRequest:
    scenario: ShutdownScenario
    code: ExitCode
    detail: str = ""


class SystemManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(
            self,
            market_clock,
            log_service: Optional[LogService] = None,
            metric_service: Optional[MetricService] = None,
            error_service: Optional[ErrorService] = None,
            notification_service: Optional[NotificationService] = None,

    ):
        if self._initialized:
            return

        self.state = SystemState()

        self._market_clock = market_clock
        self._market_clock.subscribe(self.on_market_state_change)

        #temporary
        self._logs = log_service or NullLogService()
        self._metrics = metric_service or NullMetricService()
        self._error = error_service or NullErrorService()
        self._notif = notification_service or NullNotificationService()

        self._initialized = True

    def _set_status(self, status: SystemStatus, detail: str = "") -> None:
        self.state.status = status
        self.state.since = datetime.now(timezone.utc)
        self.state.detail = detail

    def run_readiness_checks(self, checks: Iterable[ReadinessCheck]) -> list[ConnectionStatus]:
        results: list[ConnectionStatus] = []
        try:
            for check in checks:
                results.append(check.ping())
        except Exception:
            self._set_status(SystemStatus.ERROR)
            return results

        con_status = all(r.status for r in results)
        self._set_status(SystemStatus.READY if con_status else SystemStatus.ERROR)
        return results


    def shutdown(
        self,
        code: "ExitCode" = None,
        detail: str = "",
        scenario: ShutdownScenario = ShutdownScenario.UNKNOWN,
    ):

        if code is None:
            code = ExitCode.OK

        request = ShutdownRequest(scenario=scenario, code=code, detail=detail)
        self._run_shutdown(request)

    def _run_shutdown(self, request: ShutdownRequest) -> None:
        #Warning : si le shutdown leve une erreur, elle sera ignoree avec finally

        try:
            try:
                self._set_status(self.state.status, detail=request.detail)
            except Exception:
                pass

            scenario = request.scenario

            if scenario == ShutdownScenario.BOOTSTRAP_MARKET_CLOSED:
                self._shutdown_flow_bootstrap_market_closed(request)
                return

        finally:
            raise SystemExit(int(request.code))



    def _shutdown_flow_bootstrap_market_closed(self, request: ShutdownRequest) -> None:
        # TODO: séquence minimale au bootstrap (stop clock, cleanup léger, etc.)
        return

        # How to use :

        # system_manager.shutdown(
        #     scenario=ShutdownScenario.BOOTSTRAP_MARKET_CLOSED,
        #     code=ExitCode.MARKET_CLOSED_TODAY,
        #     detail="The market is closed today."
        # )



    # temporary
    def on_market_state_change(self, event: MarketStateChangeEvent):
        print(
            f"[SystemManager] Market state change: "
            f"{event.previous.name} → {event.current.name}"
        )

        return






