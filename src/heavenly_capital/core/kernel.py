import asyncio
import datetime
import threading
import time
from uuid import uuid4

from heavenly_capital.core.calendar import USMarketsCalendar
from heavenly_capital.core.clock import MarketClock, AcceleratedTimeHeartbeat, MarketStateChangeEvent, MarketState

from heavenly_capital.db.connector import DB_CONNECTOR
from heavenly_capital.db.reader import DataAccessLayer
from heavenly_capital.db.writer import DataIngestionLayer

from heavenly_capital.models.config import RuntimeConfig
from heavenly_capital.models.runtime import AsyncRuntimeModule
from heavenly_capital.models.session import SessionStatus, SessionPhase, SessionState

from heavenly_capital.models.system import (
    SystemState,
    RuntimeRegistry,
    MarketDaySession,
    BootPlan, BootDecision,
    SystemPorts, DatabasePorts,
    ShutdownScenario, ExitCode, ShutdownRequest,
)

from heavenly_capital.monitoring.error_service import NullErrorService, HealthCheckError
from heavenly_capital.monitoring.log_service import NullLogService
from heavenly_capital.monitoring.metric_service import NullMetricService
from heavenly_capital.monitoring.notification_service import NullNotificationService



heartbeat = AcceleratedTimeHeartbeat(
        day_seconds=600,
        start_timestamp=datetime.datetime(2026,1,1,0,0).timestamp())


class Kernel:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._loop = asyncio.get_event_loop()

        self.state = SystemState()

        self._market_clock = MarketClock(time_source=heartbeat)
        self._market_handlers = {
            MarketState.CLOSED: self._on_market_closed,
            MarketState.PRE_MARKET: self._on_pre_market,
            MarketState.OPEN: self._on_market_open,
            MarketState.POST_MARKET: self._on_post_market,
        }

        self._market_calendar = USMarketsCalendar()

        self._db = self._build_db_service()
        self._log = NullLogService()
        self._metrics = NullMetricService()
        self._error = NullErrorService()
        self._notif = NullNotificationService()

        self._modules = RuntimeRegistry().build()
        self._runtime_config = RuntimeConfig()

        self._modules_started = False
        self._modules_configured = False


    @staticmethod
    def _build_db_service():
        return DatabasePorts(
            writer=DataIngestionLayer(connector=DB_CONNECTOR),
            reader=DataAccessLayer(connector=DB_CONNECTOR)
        )


# region Boostrap

    async def _prepare_bootstrap(self):
        if not self._market_calendar.is_open_today():
            return self.shutdown(
                scenario=ShutdownScenario.BOOTSTRAP_MARKET_CLOSED,
                code=ExitCode.MARKET_CLOSED_TODAY,
                detail="The market is closed today."
            )

        today_session = self._build_market_day_session()
        boot_plan = self._build_boot_plan(today_session=today_session)

        await self._execute_boot_plan(boot_plan)
        return None


    def _build_market_day_session(self) -> "MarketDaySession":
        today = self._market_calendar.today()
        row = self._db.reader.get_session_by_date(today)

        if row is not None:
            return MarketDaySession.from_database(row)

        market_day_session = MarketDaySession(
            session_id=uuid4(),
            session_date=today,
            status=SessionStatus.OPEN,
            phase=SessionPhase.STRATEGIC_SETUP,
            state=SessionState.RUNNING,
            error=False
        )

        self._db.writer.persist_session(session=market_day_session)

        return market_day_session


    @staticmethod
    def _build_boot_plan(today_session: MarketDaySession) -> BootPlan:
        match (today_session.status, today_session.error, today_session.phase):

            case (SessionStatus.OPEN, False, SessionPhase.STRATEGIC_SETUP):
                return BootPlan(
                    decision=BootDecision.BOOT_NEW_SESSION,
                    session=today_session,
                    procedure="PRE_MARKET", #TODO:TEMPORARY TURN STRATEGIC_SETUP TO PRE_MARKET
                )

            case (SessionStatus.OPEN, False, SessionPhase.PRE_MARKET):
                return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure="PRE_MARKET",
                )

            case (SessionStatus.OPEN, True, SessionPhase.STRATEGIC_SETUP):
                return BootPlan(
                    decision=BootDecision.REBOOT,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case (SessionStatus.OPEN, True, SessionPhase.PRE_MARKET):
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

            case (SessionStatus.OPEN, True, SessionPhase.POST_MARKET):
                return BootPlan(
                    decision=BootDecision.RECOVERY,
                    session=today_session,
                    procedure=f"RESTART_AFTER_STOP:{today_session.phase.value}",
                )

            case _:
                raise ValueError(
                    f"Boot plan not found for status={today_session.status}, "
                    f"error={today_session.error}, phase={today_session.phase}"
                )


    async def _execute_boot_plan(self, plan: "BootPlan") -> None:
        proc = plan.procedure
        if proc == "STRATEGIC_SETUP":
            self._proc_strategic_setup(plan)
            return

        if proc == "PRE_MARKET":
            await self._proc_pre_market(plan)
            return

        if proc.startswith("RESTART_AFTER_STOP:"):
            self._proc_restart_after_stop(plan)
            return

        raise ValueError(f"Unknown procedure: {proc}")

# endregion


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
        # Warning : si le shutdown leve une erreur, elle sera ignoree avec finally
        try:
            try:
                self.state.set_status(self.state.status, detail=request.detail)
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


    def _proc_strategic_setup(self, plan: "BootPlan") -> None:
        # TODO: implémenter
        return


    async def _proc_pre_market(self, plan: "BootPlan") -> None:
        self._market_clock.subscribe_market(self.on_market_state_change)
        self._market_clock.start()


    async def _on_pre_market(self):
        print("[Kernel] PRE_MARKET triggered. Pre-market phase started.")

        await self.launch_global_runtime()
        self.launch_local_runtime()

        await self._modules.ibkr_gateway.update_account_state()
        await self._modules.ibkr_gateway.load_universe_snapshot()

        self._sync_hubs_with_contracts()
        await self.initialize_market_data_feeds()
        self._register_threads()

        await self._modules.ibkr_gateway.client_manager.start()

        await self._modules.ibkr_gateway.start_streaming()
        self._start_runtime_loop()
        await self._modules.ibkr_gateway.client_manager.wait()


    async def _on_market_closed(self):
        print("[Kernel] MARKET_CLOSED triggered. Market is now closed.")

        await self._modules.ibkr_gateway.update_account_state()
        await self._modules.ibkr_gateway.stop_streaming()

        self._modules.thread_manager.stop_thread("runtime_loop")


    async def _on_market_open(self):
        print("[Kernel] MARKET_OPEN triggered. Active trading started.")

    async def _on_post_market(self):
        print("[Kernel] POST_MARKET triggered. Post-market phase running.")



    def _proc_restart_after_stop(self, plan: "BootPlan") -> None:
        """
        Peut parser plan.procedure, ex: 'RESTART_AFTER_STOP:PRE_MARKET'
        """
        # TODO: parser la phase et appliquer la stratégie de recovery
        return



    # region Runtime

    async def launch_global_runtime(self) -> None:
        self._configure_runtime_modules()
        await self._start_runtime_modules()
        self._wire_global_runtime()
        self._health_checks_runtime_modules()


    def _build_ports(self) -> SystemPorts:
        return SystemPorts(
            market_clock=self._market_clock,
            market_calendar=self._market_calendar,
            db_service=self._db,
            log_service=self._log,
            metric_service=self._metrics,
            error_service=self._error,
            notification_service=self._notif,
        )

    def _configure_runtime_modules(self) -> None:
        if self._modules_configured:
            return

        ports = self._build_ports()

        if self._modules.thread_manager:
            self._modules.thread_manager.configure(self._runtime_config.thread, ports)

        if self._modules.ibkr_gateway:
            self._modules.ibkr_gateway.configure(self._runtime_config.ibkr, ports)

        if self._modules.historic_hub:
            self._modules.historic_hub.configure(self._runtime_config.historic_hub, ports)

        if self._modules.live_hub:
            self._modules.live_hub.configure(self._runtime_config.live_hub, ports)

        if self._modules.feature_manager:
            self._modules.feature_manager.configure(self._runtime_config.feature, ports)

        if self._modules.forecast_manager:
            self._modules.forecast_manager.configure(self._runtime_config.forecast, ports)

        if self._modules.session_manager:
            self._modules.session_manager.configure(self._runtime_config.session_manager, ports)

        self._modules_configured = True


    async def _start_runtime_modules(self) -> None:
        if self._modules_started:
            return

        modules_to_start = (
            self._modules.thread_manager,
            self._modules.ibkr_gateway,
            self._modules.historic_hub,
            self._modules.live_hub,
            self._modules.forecast_manager,
            self._modules.feature_manager,
            self._modules.session_manager
        )

        for module in modules_to_start:
            if module is not None:
                if isinstance(module, AsyncRuntimeModule):
                    await module.start()
                else:
                    module.start()

        self._modules_started = True


    def _health_checks_runtime_modules(self) -> None:
        modules_to_check = (
            self._modules.ibkr_gateway,
            self._modules.historic_hub,
            self._modules.live_hub,
            self._modules.feature_manager,
            self._modules.forecast_manager,
            self._modules.thread_manager,
            self._modules.session_manager
        )

        #TODO:LOW - Finish the health check for the modules
        results = [m.health_check() for m in modules_to_check if m is not None]
        failed_results = [r for r in results if r.get("is_healthy") is not True]

        if failed_results:
            raise HealthCheckError(results)


    def launch_local_runtime(self) -> None:
        self._modules.session_manager.initialize_sessions_from_config()
        self._modules.session_manager.load_sessions_state_from_database()
        self._modules.session_manager.health_check_loaded_sessions()

        self._wire_local_runtime()


    # endregion

    # region Wiring

    def _wire_global_runtime(self) -> None:
        self._wire_order_router_to_session_manager()
        self._wire_gateway_sink_to_live_hub()
        self._wire_live_hub_to_historic_hub()
        self._wire_historic_hub_to_feature_manager()
        self._wire_feature_store_to_forecast_manager()



    def _wire_order_router_to_session_manager(self) -> None:
        sink = self._modules.ibkr_gateway.order_sink
        self._modules.session_manager.wire_order_router(sink=sink)

    def _wire_gateway_sink_to_live_hub(self) -> None:
        ticker_sink = self._modules.live_hub.ingest_port
        self._modules.ibkr_gateway.wire_live_ticker(ticker_sink)

    def _wire_live_hub_to_historic_hub(self) -> None:
        candle_bus = self._modules.live_hub.candle_bus
        self._modules.historic_hub.wire_live_ohlc_bus(candle_bus)

    def _wire_historic_hub_to_feature_manager(self) -> None:
        candle_bus = self._modules.historic_hub.out_bus
        self._modules.feature_manager.wire_historic_candle_bus(candle_bus)

    def _wire_feature_store_to_forecast_manager(self) -> None:
        store = self._modules.feature_manager.out_queue
        self._modules.forecast_manager.wire_feature_store(store)



    def _wire_local_runtime(self) -> None:
        self._wire_live_hub_to_local_runtime()
        self._wire_forecast_manager_to_local_runtime()

    def _wire_live_hub_to_local_runtime(self) -> None:
        tickers = self._modules.live_hub.tickers
        for session in self._modules.session_manager.sessions.values():
            session.wire_live_tickers(tickers)

    def _wire_forecast_manager_to_local_runtime(self) -> None:
        forecast_bus = self._modules.forecast_manager.bus_out
        for session in self._modules.session_manager.sessions.values():
            session.wire_forecast_signal(forecast_bus)

    # endregion

    async def initialize_market_data_feeds(self):
        self._modules.feature_manager.build_market_data_banks()
        self._modules.feature_manager.subscribe_to_live_candle()
        self._modules.historic_hub.subscribe_to_live_candle()
        self._modules.forecast_manager.setup_models_and_store()


    def _sync_hubs_with_contracts(self) -> None:
        contracts = self._modules.ibkr_gateway.contracts

        self._modules.live_hub.initialize_pipelines(contracts)

        modules = [
            self._modules.historic_hub,
            self._modules.feature_manager,
            self._modules.forecast_manager
        ]

        for m in modules:
            m.initialize_universe(contracts)

        for session in self._modules.session_manager.sessions.values():
            session.load_contracts(contracts)


    def _runtime_tick(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            now = time.time()

            self._modules.live_hub.aggregate_and_publish_candles(current_time=now)
            self._modules.historic_hub.ingest_candle_5s()
            self._modules.historic_hub.dispatch_candle_events()
            self._modules.feature_manager.process_candle_events()
            self._modules.forecast_manager.run_predictions()


    def _register_threads(self) -> None:
        tm = self._modules.thread_manager
        tm.register_thread(
            name="runtime_loop",
            target=self._runtime_tick,
            daemon=False
        )

    def _start_runtime_loop(self) -> None:
        self._modules.thread_manager.start_thread("runtime_loop")


    def on_market_state_change(self, event: MarketStateChangeEvent):
        handler = self._market_handlers.get(event.current)
        if handler:
            asyncio.run_coroutine_threadsafe(handler(), self._loop)

        t = datetime.datetime.fromtimestamp(event.timestamp)
        print(f"[Kernel] Market state change: "
            f"{event.previous.name} -> {event.current.name} at {t}"
        )

        return
















    # def run_readiness_checks(self, checks: Iterable[ReadinessCheck]) -> list[ConnectionStatus]:
    #     results: list[ConnectionStatus] = []
    #     try:
    #         for check in checks:
    #             results.append(check.ping())
    #     except Exception:
    #         self._set_status(SystemStatus.ERROR)
    #         return results
    #
    #     con_status = all(r.status for r in results)
    #     self._set_status(SystemStatus.READY if con_status else SystemStatus.ERROR)
    #     return results





