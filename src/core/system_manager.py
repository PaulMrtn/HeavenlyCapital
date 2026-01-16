 # core/system_manager.py

from __future__ import annotations

import threading
from typing import Optional, Iterable, Any, Mapping, Protocol, runtime_checkable

from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from uuid import UUID, uuid4

from src.core.runtime_config import RuntimeConfig, RuntimeModule
from src.core.market_clock import MarketStateChangeEvent
from src.core.runtime_config import get_global_runtime_config
from src.core.thread_manager import ThreadManager
from src.strategy.forecast_manager import ForecastManager
from src.data.live_data_hub import LiveDataHub
from src.data.historic_data_hub import HistoricDataHub
from src.trading.ibkr_gateway import IBKRGateway
from src.core.session_manager import SessionManager

from src.data.data_access import DataAccessLayer
from src.data.data_ingestion import DataIngestionLayer

from src.monitoring.error_service import NullErrorService, ErrorService, HealthCheckError
from src.monitoring.log_service import LogService, NullLogService
from src.monitoring.metric_service import MetricService, NullMetricService
from src.monitoring.notification_service import NullNotificationService, NotificationService
from src.monitoring.health_checks import ConnectionStatus, ReadinessCheck


#region System DataClass

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

#endregion


#region MarketDaySession DataClass
class SessionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class SessionPhase(str, Enum):
    STRATEGIC_SETUP = "STRATEGIC_SETUP"
    PRE_MARKET = "PRE_MARKET"
    IN_MARKET = "IN_MARKET"
    POST_MARKET = "POST_MARKET"

class SessionState(str, Enum):
    DONE = "DONE"
    RUNNING = "RUNNING"

@dataclass(slots=True)
class MarketDaySession:
    session_id: UUID
    session_date: date
    status: SessionStatus
    phase: SessionPhase
    state : SessionState
    error: bool = False

#endregion


#region Boot DataClass
class BootDecision(str, Enum):
    BOOT_NEW_SESSION = "BOOT_NEW_SESSION"
    START_TRADING_SESSION = "START_TRADING_SESSION"
    REBOOT = "REBOOT"
    RECOVERY = "RECOVERY"


@dataclass(slots=True)
class BootPlan:
    decision: BootDecision
    session: MarketDaySession
    procedure: str  #  ex: "PRE_MARKET", "STRATEGIC_SETUP", "RECOVERY:<phase>"

#endregion


# region GlobalRuntime DataClass
class MarketPorts(Protocol):
    market_clock: Any
    market_calendar: Any


class StoragePorts(Protocol):
    data_ingestion: Any
    data_access: Any


class ObservabilityPorts(Protocol):
    log_service: Any
    metric_service: Any
    error_service: Any
    notification_service: Any


# Optionnel: une vue "complète" si certains modules ont vraiment besoin de tout
class FullSystemPorts(MarketPorts, StoragePorts, ObservabilityPorts, Protocol):
    pass


@dataclass(frozen=True, slots=True)
class SystemPorts:
    market_clock: Any
    market_calendar: Any

    data_ingestion: Any
    data_access: Any

    log_service: Any
    metric_service: Any
    error_service: Any
    notification_service: Any


@dataclass(slots=True)
class RuntimeRegistry:
    ibkr_gateway: Optional[RuntimeModule | IBKRGateway] = None
    historic: Optional[RuntimeModule | HistoricDataHub] = None
    live_hub: Optional[RuntimeModule | LiveDataHub] = None
    forecast_manager: Optional[RuntimeModule | ForecastManager] = None
    thread_manager: Optional[RuntimeModule | ThreadManager] = None
    session_manager: Optional[RuntimeModule | SessionManager] = None


# endregion


class SystemManager:
    _instance = None

    # TODO : CHECK DE TOUT LES THREADS
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
            market_calendar,

            data_ingestion: DataIngestionLayer,
            data_access: DataAccessLayer,

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
        self._market_calendar = market_calendar

        # self._data_service = DataServices(dil, dal)
        self._data_ingestion = data_ingestion
        self._data_access = data_access

        # obs = Observability (log, metrics, error, notif)
        self._logs = log_service or NullLogService()
        self._metrics = metric_service or NullMetricService()
        self._error = error_service or NullErrorService()
        self._notif = notification_service or NullNotificationService()

        self.trading_session: MarketDaySession | None = None
        self._active_trading_day = None


        self._modules = RuntimeRegistry()
        self._runtime_config = RuntimeConfig()
        self._modules_configured = False
        self._modules_started = False


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




#region Bootstrap
    def _build_boot_plan(self, today_session : None | MarketDaySession) -> BootPlan | None:

        if today_session is None:
            today_session = MarketDaySession(
                session_id=uuid4(),
                session_date=self._market_calendar.today(),
                status=SessionStatus.OPEN,
                phase=SessionPhase.STRATEGIC_SETUP,
                state=SessionState.RUNNING,
                error=False
            )
            return BootPlan(
                decision=BootDecision.BOOT_NEW_SESSION,
                session=today_session,
                procedure="STRATEGIC_SETUP",
            )

        match (today_session.status, today_session.error, today_session.phase):

            case (SessionStatus.OPEN, False, SessionPhase.PRE_MARKET):
                 return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure="PRE_MARKET",
                )

            case(SessionStatus.OPEN, True, SessionPhase.STRATEGIC_SETUP):
                return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case(SessionStatus.OPEN, True, SessionPhase.PRE_MARKET):
                return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case (SessionStatus.OPEN, True, SessionPhase.IN_MARKET):
                return BootPlan(
                    decision=BootDecision.RECOVERY,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case(SessionStatus.OPEN, True, SessionPhase.POST_MARKET):
                return BootPlan(
                    decision=BootDecision.RECOVERY,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case _:
                raise ValueError(
                    f"Boot plan introuvable pour status={today_session.status}, "
                    f"error={today_session.error}, phase={today_session.phase}"
                )


    def _execute_boot_plan(self, plan: "BootPlan") -> None:
        proc = plan.procedure

        if proc == "STRATEGIC_SETUP":
            self._proc_strategic_setup(plan)
            return

        if proc == "PRE_MARKET":
            self._proc_pre_market(plan)
            return

        if proc.startswith("RESTART_AFTER_STOP:"):
            self._proc_restart_after_stop(plan)
            return

        raise ValueError(f"Procédure inconnue: {proc}")


    def _proc_strategic_setup(self, plan: "BootPlan") -> None:
        # TODO: implémenter
        return


    def _proc_pre_market(self, plan: "BootPlan") -> None:
        # TODO: to continue
        self.launch_global_runtime()
        # self.launch_local_runtime()
        return


    def _proc_restart_after_stop(self, plan: "BootPlan") -> None:
        """
        Peut parser plan.procedure, ex: 'RESTART_AFTER_STOP:PRE_MARKET'
        """
        # TODO: parser la phase et appliquer la stratégie de recovery
        return


    def _prepare_bootstrap(self, checks):
        self.run_readiness_checks(checks=checks)

        # TODO : add / remove not in prod
        if not self._market_calendar.is_open_today() :
            return self.shutdown(
            scenario=ShutdownScenario.BOOTSTRAP_MARKET_CLOSED,
            code=ExitCode.MARKET_CLOSED_TODAY,
            detail="The market is closed today."
            )

        # TODO: récupérer la session du jour via DAL quand prêt
        today_session = None  # ex: self._data_access.get_by_date(self._market_calendar.today())
        boot_plan = self._build_boot_plan(today_session=today_session)
        # self.persist_session(session=boot_plan.session)

        self._execute_boot_plan(boot_plan)
        return None

#endregion




# region Shutdown
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

# endregion




# region TemporaryFunction
    def on_market_state_change(self, event: MarketStateChangeEvent):
        print(
            f"[SystemManager] Market state change: "
            f"{event.previous.name} → {event.current.name}"
        )
        return


    # TODO : Priority with duckDN or/with postgresDB,
    def persist_session(
            self,
            session: MarketDaySession,
            *,
            patch: Optional[Mapping[str, Any]] = None,
            note: Optional[str] = None,
        ) -> None:

            if patch:
                for k, v in patch.items():
                    setattr(session, k, v)

            existed = self._data_ingestion.exists_for_date(session.session_date)
            if existed:
                self._data_ingestion.update(session)
            else:
                self._data_ingestion.insert(session)

    # endregion




# region GlobalRuntimeLauncher

    def _set_runtime_config(self, config: RuntimeConfig) -> None:
        self._runtime_config = config
        self._modules_configured = False

    def _attach_runtime_modules(
            self,
            *,
            ibkr_gateway: Optional[RuntimeModule | IBKRGateway],
            historic_data_hub: Optional[RuntimeModule | HistoricDataHub],
            live_data_hub: Optional[RuntimeModule | LiveDataHub],
            forecast_manager: Optional[RuntimeModule | ForecastManager],
            thread_manager: Optional[RuntimeModule | ThreadManager],
            session_manager: Optional[RuntimeModule | SessionManager],
    ) -> None:

        self._modules.ibkr_gateway = ibkr_gateway
        self._modules.historic = historic_data_hub
        self._modules.live_hub = live_data_hub
        self._modules.forecast_manager = forecast_manager
        self._modules.thread_manager = thread_manager
        self._modules.session_manager = session_manager
        self._modules_configured = False

    def _build_ports(self) -> SystemPorts:
        return SystemPorts(
            market_clock=self._market_clock,
            market_calendar=self._market_calendar,
            data_ingestion=self._data_ingestion,
            data_access=self._data_access,
            log_service=self._logs,
            metric_service=self._metrics,
            error_service=self._error,
            notification_service=self._notif,
        )

    def _configure_runtime_modules(self) -> None:
        if self._modules_configured:
            return

        ports = self._build_ports()

        modules_to_configure = (
            (self._modules.ibkr_gateway, self._runtime_config.ibkr),
            (self._modules.historic, self._runtime_config.historic),
            (self._modules.live_hub, self._runtime_config.live_hub),
            (self._modules.forecast_manager, self._runtime_config.forecast),
            (self._modules.thread_manager, self._runtime_config.thread),
            (self._modules.session_manager, self._runtime_config.session_manager)
        )

        for module, config in modules_to_configure:
            if module is not None:
                module.configure(config=config, ports=ports)

        self._modules_configured = True

    def _start_runtime_modules(self) -> None:
        if self._modules_started:
            return

        modules_to_start = (
            self._modules.ibkr_gateway,
            self._modules.historic,
            self._modules.live_hub,
            self._modules.forecast_manager,
            self._modules.thread_manager,
            self._modules.session_manager
        )

        for module in modules_to_start:
            if module is not None:
                module.start()

        self._modules_started = True

    def _wire_runtime_modules(self) -> None:
        self._wire_routing()

    def _wire_routing(self) -> None:
        sink = self._modules.ibkr_gateway.order_sink
        self._modules.session_manager.init_router(sink=sink)


    def _health_checks_runtime_modules(self) -> None:
        modules_to_check = (
            self._modules.ibkr_gateway,
            self._modules.historic,
            self._modules.live_hub,
            self._modules.forecast_manager,
            self._modules.thread_manager,
            self._modules.session_manager
        )

        results = [m.health_check() for m in modules_to_check if m is not None]
        failed_results = [r for r in results if r.get("is_healthy") is not True]

        if failed_results:
            raise HealthCheckError(results)

    def launch_global_runtime(self) -> None:
        # TODO : handle this import
        from src.strategy.forecast_manager import get_forecast_manager
        from src.data.live_data_hub import get_live_data_hub
        from src.data.historic_data_hub import get_historic_data_hub
        from src.trading.ibkr_gateway import get_ibkr_gateway
        from src.core.thread_manager import get_thread_manager
        from src.core.session_manager import get_session_manager

        # TODO : handle this import to
        runtime_config = get_global_runtime_config()
        self._set_runtime_config(runtime_config)

        self._attach_runtime_modules(
            ibkr_gateway=get_ibkr_gateway(),
            historic_data_hub=get_historic_data_hub(),
            live_data_hub=get_live_data_hub(),
            forecast_manager=get_forecast_manager(),
            thread_manager=get_thread_manager(),
            session_manager=get_session_manager()
        )

        self._configure_runtime_modules()
        self._start_runtime_modules()
        self._health_checks_runtime_modules()
        self._wire_runtime_modules()

    # endregion



# region LocalRuntimeLauncher


    def launch_local_runtime(self) : ...




# endregion