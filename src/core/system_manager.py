 # core/system_manager.py

from __future__ import annotations

import threading
from typing import Optional, Protocol, Iterable, Any, Mapping
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from uuid import UUID, uuid4

from src.core.runtime_config import ConfigurableModule, RuntimeConfig, Startable
from src.core.market_clock import MarketStateChangeEvent

from src.data.data_access import DataAccessLayer
from src.data.data_ingestion import DataIngestionLayer

from src.monitoring.error_service import NullErrorService, ErrorService
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

#region TradingSession DataClass
class TradingSessionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class TradingSessionPhase(str, Enum):
    STRATEGIC_SETUP = "STRATEGIC_SETUP"
    PRE_MARKET = "PRE_MARKET"
    IN_MARKET = "IN_MARKET"
    POST_MARKET = "POST_MARKET"

class TradingSessionState(str, Enum):
    DONE = "DONE"
    RUNNING = "RUNNING"


@dataclass(slots=True)
class TradingSession:
    session_id: UUID
    session_date: date
    status: TradingSessionStatus
    phase: TradingSessionPhase
    state : TradingSessionState
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
    session: TradingSession
    procedure: str  #  ex: "PRE_MARKET", "STRATEGIC_SETUP", "RECOVERY:<phase>"

#endregion


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
class RuntimeModules:
    ibkr_gateway: Optional[ConfigurableModule] = None
    historic: Optional[ConfigurableModule] = None
    live_hub: Optional[ConfigurableModule] = None
    forecast_manager: Optional[ConfigurableModule] = None


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

        self.trading_session: TradingSession | None = None
        self._active_trading_day = None


        self._modules = RuntimeModules()
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

#region Bootsrap
    def _build_boot_plan(self, today_session : None | TradingSession) -> BootPlan | None:

        if today_session is None:
            today_session = TradingSession(
                session_id=uuid4(),
                session_date=self._market_calendar.today(),
                status=TradingSessionStatus.OPEN,
                phase=TradingSessionPhase.STRATEGIC_SETUP,
                state=TradingSessionState.RUNNING,
                error=False
            )
            return BootPlan(
                decision=BootDecision.BOOT_NEW_SESSION,
                session=today_session,
                procedure="STRATEGIC_SETUP",
            )

        match (today_session.status, today_session.error, today_session.phase):

            case (TradingSessionStatus.OPEN, False, TradingSessionPhase.PRE_MARKET):
                 return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure="PRE_MARKET",
                )

            case(TradingSessionStatus.OPEN, True, TradingSessionPhase.STRATEGIC_SETUP):
                return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case(TradingSessionStatus.OPEN, True, TradingSessionPhase.PRE_MARKET):
                return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case (TradingSessionStatus.OPEN, True, TradingSessionPhase.IN_MARKET):
                return BootPlan(
                    decision=BootDecision.RECOVERY,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case(TradingSessionStatus.OPEN, True, TradingSessionPhase.POST_MARKET):
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
        # TODO: implémenter
        return


    def _proc_restart_after_stop(self, plan: "BootPlan") -> None:
        """
        Peut parser plan.procedure, ex: 'RESTART_AFTER_STOP:PRE_MARKET'
        """
        # TODO: parser la phase et appliquer la stratégie de recovery
        return


    def _prepare_bootstrap(self, checks):
        self.run_readiness_checks(checks=checks)

        if self._market_calendar.is_open_today() :
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

    def persist_session(
            self,
            session: TradingSession,
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


    # temporary
    def on_market_state_change(self, event: MarketStateChangeEvent):
        print(
            f"[SystemManager] Market state change: "
            f"{event.previous.name} → {event.current.name}"
        )
        return



# region Global Manager

    def set_runtime_config(self, config: RuntimeConfig) -> None:
        self._runtime_config = config
        self._modules_configured = False

    def attach_ibkr_gateway(self, module: ConfigurableModule) -> None:
        self._modules.ibkr_gateway = module
        self._modules_configured = False

    def attach_historic(self, module: ConfigurableModule) -> None:
        self._modules.historic = module
        self._modules_configured = False

    def attach_live_hub(self, module: ConfigurableModule) -> None:
        self._modules.live_hub = module
        self._modules_configured = False

    def attach_forecast_manager(self, module: ConfigurableModule) -> None:
        self._modules.forecast_manager = module
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

    def configure_runtime_modules(self) -> None:
        if self._modules_configured:
            return

        ports = self._build_ports()

        if self._modules.ibkr_gateway is not None:
            self._modules.ibkr_gateway.configure(config=self._runtime_config.ibkr, ports=ports)

        if self._modules.historic is not None:
            self._modules.historic.configure(config=self._runtime_config.historic, ports=ports)

        if self._modules.live_hub is not None:
            self._modules.live_hub.configure(config=self._runtime_config.live_hub, ports=ports)

        if self._modules.forecast_manager is not None:
            self._modules.forecast_manager.configure(config=self._runtime_config.forecast, ports=ports)

        self._modules_configured = True

    def start_runtime_modules(self) -> None:
        if self._modules_started:
            return

        self.configure_runtime_modules()

        if self._runtime_config.ibkr and self._modules.ibkr_gateway is not None:
            if isinstance(self._modules.ibkr_gateway, Startable):
                self._modules.ibkr_gateway.start()

        if self._runtime_config.historic.enabled and self._modules.historic is not None:
            if isinstance(self._modules.historic, Startable):
                self._modules.historic.start()

        if self._runtime_config.live_hub.enabled and self._modules.live_hub is not None:
            if isinstance(self._modules.live_hub, Startable):
                self._modules.live_hub.start()

        if self._runtime_config.forecast.enabled and self._modules.forecast_manager is not None:
            if isinstance(self._modules.forecast_manager, Startable):
                self._modules.forecast_manager.start()

        self._modules_started = True

# endregion

