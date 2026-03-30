import asyncio
import datetime
import threading
import time
from typing import Callable, Coroutine
from uuid import uuid4

from heavenly_capital.core.calendar import USMarketsCalendar
from heavenly_capital.core.clock import (
    MarketClock, AcceleratedTimeHeartbeat,
    MarketEventChangeEvent, MarketState,)

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
    ShutdownScenario, ExitCode, ShutdownRequest, SystemStatus,
)

from heavenly_capital.monitoring.error_service import NullErrorService, HealthCheckError
from heavenly_capital.monitoring.log_service import NullLogService
from heavenly_capital.monitoring.metric_service import NullMetricService
from heavenly_capital.monitoring.notification_service import NullNotificationService



heartbeat = AcceleratedTimeHeartbeat(
        day_seconds=120,
        start_timestamp=datetime.datetime(2026,1,1,3,50).timestamp())



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

        self._loop = asyncio.get_event_loop() # TODO: Handle this ( property ? )

        self._system_state = SystemState()
        self._today_session: MarketDaySession | None = None
        self._pre_market_event = asyncio.Event() # TODO: Handle this ( property ? )

        self._market_clock = MarketClock(time_source=heartbeat)
        self._market_clock.subscribe_market(self.on_market_state_change)
        self._market_clock.start()

        self._market_calendar = USMarketsCalendar()

        self._db = self._build_db_service()
        self._log = NullLogService()
        self._metrics = NullMetricService()
        self._error = NullErrorService()
        self._notif = NullNotificationService()

        self._modules = RuntimeRegistry().build()
        self._runtime_config = RuntimeConfig()

        self._market_handlers = self._build_market_handlers()

        self._modules_started = False
        self._modules_configured = False


    @staticmethod
    def _build_db_service():
        return DatabasePorts(
            writer=DataIngestionLayer(connector=DB_CONNECTOR),
            reader=DataAccessLayer(connector=DB_CONNECTOR)
        )



# region Console


    def _start_console(self):
        pass




    def _stop_console(self):
        pass



# endregion


# region Event Driven

    def _update_session(
            self,
            phase: SessionPhase | None = None,
            status: SessionStatus | None = None,
            state: SessionState | None = None,
            error: bool | None = None
    ):
        if phase:
            self._today_session.phase = phase
        if status:
            self._today_session.status = status
        if state:
            self._today_session.state = state
        if error is not None:
            self._today_session.error = error

        self._db.writer.update_session(self._today_session)


    def on_market_state_change(self, event: MarketEventChangeEvent) -> None:
        handler = self._market_handlers.get(event.current)
        if handler:
            asyncio.run_coroutine_threadsafe(handler(), self._loop)
        return


    def _build_market_handlers(self) -> dict[MarketState, Callable[[], Coroutine]]:
        return {
            MarketState.PRE_MARKET: self._on_pre_market,
            MarketState.OPEN: self._on_market_open,
            MarketState.POST_MARKET: self._on_post_market,
            MarketState.CLOSED: self._on_market_closed,
        }

    async def _on_pre_market(self):
        self._pre_market_event.set()

    async def _on_market_open(self):
        pass

    async def _on_post_market(self):
        pass

    async def _on_market_closed(self):
        await self.stop_market_runtime()

        self._update_session(state=SessionState.SHUTDOWN,
                             status=SessionStatus.COMPLETED)

        self.shutdown(
            scenario=ShutdownScenario.MARKET_SETUP_DONE,
            code=ExitCode.MARKET_SETUP_COMPLETED,
            detail="Market session completed"
        )

# endregion


# region Boostrap

    async def _prepare_bootstrap(self):
        today = self._market_calendar.today()
        row = self._db.reader.get_session_by_date(today)

        if row is None:
            if self._market_calendar.is_open_today():
                return self.shutdown(
                    scenario=ShutdownScenario.BOOTSTRAP_MARKET_CLOSED,
                    code=ExitCode.MARKET_CLOSED_TODAY,
                    detail="The market is closed today."
                )
            self._today_session = self._build_market_day_session()
        else:
            self._today_session = MarketDaySession.from_database(row)

        boot_plan = self._build_boot_plan()
        await self._execute_boot_plan(boot_plan)

        return None


    def _build_market_day_session(self) -> "MarketDaySession":
        today = self._market_calendar.today()
        row = self._db.reader.get_session_by_date(today)

        if row is not None:
            return MarketDaySession.from_database(row)

        today_session = MarketDaySession(
            session_id=uuid4(),
            session_date=today,
            status=SessionStatus.IN_PROGRESS,
            phase=SessionPhase.STRATEGIC_SETUP, # TODO: WTF
            state=SessionState.INITIALIZATION,
            error=False
        )

        self._db.writer.update_session(session=today_session)

        return today_session


    def _build_boot_plan(self) -> BootPlan:
        match (self._today_session.status, self._today_session.error, self._today_session.phase):

            case (SessionStatus.IN_PROGRESS, False, SessionPhase.STRATEGIC_SETUP):
                return BootPlan(
                    decision=BootDecision.BOOT,
                    procedure="STRATEGIC_SETUP",
                )

            case (SessionStatus.COMPLETED, False, SessionPhase.STRATEGIC_SETUP):
                return BootPlan(
                    decision=BootDecision.BOOT,
                    procedure="MARKET_SETUP",
                )


            case _:
                raise ValueError(
                    f"Boot plan not found for status={self._today_session.status}, "
                    f"error={self._today_session.error}, phase={self._today_session.phase}"
                )


    async def _execute_boot_plan(self, plan: "BootPlan") -> None:

        self._system_state.set_status(SystemStatus.RUNNING)

        proc = plan.procedure

        if proc == "STRATEGIC_SETUP":
            self._strategic_setup()
            # await self._run_procedure(self._strategic_setup)
            return

        if proc == "MARKET_SETUP":
            await self._market_setup()
            # await self._run_procedure(self._market_setup)
            return

        raise ValueError(f"Unknown procedure: {proc}")

# endregion


# region Shutdown
    def shutdown(
            self,
            code: "ExitCode",
            scenario: "ShutdownScenario",
            detail: str = "",
    ):

        if code is None:
            code = ExitCode.OK

        request = ShutdownRequest(scenario=scenario, code=code, detail=detail)
        self._run_shutdown(request)

    def _run_shutdown(self, request: ShutdownRequest) -> None:
        # Warning : si le shutdown leve une erreur, elle sera ignoree avec finally
        try:
            self._system_state.set_status(SystemStatus.STOPPING, detail=request.detail)

            scenario = request.scenario

            # TODO:LOW - shutdown task sequences are necessary ?

            if scenario == ShutdownScenario.BOOTSTRAP_MARKET_CLOSED:
                self._shutdown_task_bootstrap_market_closed(request)
                return

            if scenario == ShutdownScenario.MARKET_SETUP_DONE:
                self._shutdown_task_market_completed(request)
                return

            if scenario == ShutdownScenario.STRATEGIC_SETUP_DONE:
                self._shutdown_task_strategy_completed(request)
                return

        finally:
            raise SystemExit(int(request.code))

    def _shutdown_task_bootstrap_market_closed(self, request: ShutdownRequest) -> None:
        #TODO:LOW - List of tasks to perform before the main process shutdown
        return

    def _shutdown_task_strategy_completed(self, request: ShutdownRequest) -> None:
        return

    def _shutdown_task_market_completed(self, request: ShutdownRequest) -> None:
        return


# endregion


# region Procedures
    async def _run_procedure(self, proc: Callable, *args, **kwargs):

        try:
            result = proc(*args, **kwargs)

            if asyncio.iscoroutine(result):
                await result

            return result

        except Exception as e:
            print(e)

            self._system_state.set_status(SystemStatus.ERROR, detail=str(e))

            self._update_session(error=True)

            self.shutdown(
                scenario=ShutdownScenario.PROCEDURE_FAILED,
                code=ExitCode.ERROR,
                detail=str(e)
            )


    def _strategic_setup(self) -> None:

        self._update_session(state=SessionState.RUNNING)

        time.sleep(0.3)

        self._update_session(state=SessionState.SHUTDOWN,
                             status=SessionStatus.COMPLETED)

        self.shutdown(
            scenario=ShutdownScenario.STRATEGIC_SETUP_DONE,
            code=ExitCode.STRATEGIC_SETUP_COMPLETED,
            detail="Strategic session completed"
        )

        return


    async def _market_setup(self) -> None:

        self._update_session(
            state=SessionState.INITIALIZATION,
            status=SessionStatus.IN_PROGRESS,
            phase=SessionPhase.MARKET_SETUP)

        await self.initialize_market_setup()

        self._update_session(
            state=SessionState.STAND_BY)

        await self._pre_market_event.wait()

        self._update_session(
            state=SessionState.RUNNING)

        await self.start_market_runtime()


    def _restart_after_stop(self) -> None:
        # TODO:LOW - Recovery strategy ?
        return


# endregion


# region MARKET_SETUP

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

        self._wire_local_runtime()

        self._modules.session_manager.load_sessions_portfolio_orders()
        self._modules.session_manager.health_check_loaded_sessions()


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


    async def initialize_market_setup(self) -> None:
        await self.launch_global_runtime()
        self.launch_local_runtime()

        await self._modules.ibkr_gateway.update_account_state()
        await self._modules.ibkr_gateway.load_universe_snapshot()

        self._sync_hubs_with_contracts()
        await self.initialize_market_data_feeds()
        self._register_threads()

        await self._modules.ibkr_gateway.client_manager.start()



    async def start_market_runtime(self) -> None:
        await self._modules.ibkr_gateway.start_streaming()

        self._start_threads()

        await self._modules.ibkr_gateway.client_manager.wait()


    async def stop_market_runtime(self) -> None:
        self._update_session(state=SessionState.SETTLING)

        await self._modules.ibkr_gateway.update_account_state()
        await self._modules.ibkr_gateway.stop_streaming()

        self._stop_threads()



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


# region Threads

    def _register_threads(self) -> None:
        tm = self._modules.thread_manager
        tm.register_thread(
            name="runtime_loop",
            target=self._runtime_tick,
            daemon=False
        )

        tm.register_thread(
            name="db_writer",
            daemon=True
        )

    def _start_threads(self) -> None:
        tm = self._modules.thread_manager

        tm.start_thread("db_writer")
        tm.start_thread("order_router")
        tm.start_thread("runtime_loop")

    def _stop_threads(self) -> None:
        tm = self._modules.thread_manager

        tm.stop_thread("runtime_loop")
        tm.stop_thread("order_router")
        tm.stop_thread("db_writer")


    # endregion



