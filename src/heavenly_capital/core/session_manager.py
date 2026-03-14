from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from datetime import date
from enum import Enum
from threading import Condition, RLock, Thread
from typing import Any, Callable, Deque, Dict, Optional, TYPE_CHECKING
from uuid import uuid4, UUID

from heavenly_capital.core.runtime_config import SessionConfig, ModuleRouter, ModuleType
from heavenly_capital.core.kernel import RuntimeModule
from heavenly_capital.models.market_data import ReadOnlyTicker, TickerManager
from heavenly_capital.models.order import OrderRequest, OrderTracker
from heavenly_capital.monitoring.error_service import HealthCheckError
from heavenly_capital.trading.router import GlobalOrderRouter

from heavenly_capital.trading.order_manager import OrderManager
from heavenly_capital.trading.portfolio_manager import PortfolioManager
from heavenly_capital.trading.risk_manager import RiskManager


if TYPE_CHECKING:
    from heavenly_capital.core.kernel import SystemPorts



class TradingMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class SessionState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class TradingSessionKey:
    session_date: date
    account_id: str
    portfolio_id: str
    mode: TradingMode



class TradingEngine(ModuleRouter):

    def __init__(
            self,
            orders: BaseModule,
            portfolio: BaseModule,
            risk: BaseModule,
    ) -> None:
        self._modules: Dict[ModuleType, BaseModule] = {
            ModuleType.ORDERS: orders,
            ModuleType.PORTFOLIO: portfolio,
            ModuleType.RISK: risk,
        }

        for module_type, module in self._modules.items():
            module.bind_router(self, module_type)

    def transfer(
            self,
            *,
            source: ModuleType,
            target: ModuleType,
            payload: Any,
    ) -> None:
        if source == target:
            return

        target_module = self._modules[target]
        target_module.receive(payload, source)

    @property
    def orders(self):
        return self._modules[ModuleType.ORDERS]

    @property
    def portfolio(self):
        return self._modules[ModuleType.PORTFOLIO]

    @property
    def risk(self):
        return self._modules[ModuleType.RISK]




@dataclass
class MarketDaySessionSnapshot:
    #TODO:MEDIUM useless ?
    session_date: date
    account_id: str
    mode: str
    state: str
    created_at_utc: str
    updated_at_utc: str
    payload: Dict[str, Any]




class TradingSession:
    def __init__(
        self,
        *,
        key: TradingSessionKey,
        router: "GlobalOrderRouter",
        ports: Optional["SystemPorts"] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:

        self.key = key
        self.session_id: UUID = uuid4()
        self.state: SessionState = SessionState.IDLE

        self._payload: Dict[str, Any] = payload or {}
        self._ports: Optional["SystemPorts"] = ports
        self._order_router: "GlobalOrderRouter" = router

        self.stack: Optional[TradingEngine] = None

    @property
    def ports(self) -> "SystemPorts":
        return self._ports

    @property
    def router(self) -> "GlobalOrderRouter":
        return self._order_router

    @staticmethod
    def _build_modules() -> tuple["OrderManager", "PortfolioManager", "RiskManager"]:
        orders = OrderManager()
        portfolio = PortfolioManager()
        risk = RiskManager()
        return orders, portfolio, risk

    def _inject_modules(self, *, orders: "OrderManager", portfolio: "PortfolioManager", risk: "RiskManager") -> None:
        for m in (orders, portfolio, risk):
            m.configure(session_id=self.session_id, key=self.key, ports=self.ports)

    def initialize_modules(self) -> None:
        orders, portfolio, risk = self._build_modules()

        self._inject_modules(
            orders=orders,
            portfolio=portfolio,
            risk=risk
        )

        orders.set_order_router(self.router)

        self.stack = TradingEngine(
            orders=orders,
            portfolio=portfolio,
            risk=risk
        )

    def start(self) -> None:
        if self.state in (SessionState.RUNNING, SessionState.CLOSED):
            return
        self.state = SessionState.RUNNING

    def stop(self) -> None:
        if self.state != SessionState.RUNNING:
            return
        self.state = SessionState.STOPPED

    def close(self) -> None:
        if self.state == SessionState.CLOSED:
            return
        self.state = SessionState.CLOSED

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

    # TODO: Check the utility of this function
    def snapshot(self) -> MarketDaySessionSnapshot:
        return MarketDaySessionSnapshot(
            session_date=self.key.session_date,
            account_id=self.key.account_id,
            mode=self.key.mode.value,
            state=self.state.value,
            payload=dict(self._payload),
        )

    def load_contracts(self, contracts: dict[str, "Contract"]) -> None:
        self.stack.orders.load_contracts(contracts)

    def wire_live_tickers(self, ticker_manager: "TickerManager") -> None:
        self.stack.portfolio.wire_ticker_manager(ticker_manager)
        self.stack.risk.wire_ticker_manager(ticker_manager)

    def wire_forecast_signal(self, bus: "EventBus"):
        self.stack.portfolio.wire_forecast_manager(bus)
        # self.stack.risk.wire_forecast_manager(bus)




class SessionManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional["SessionConfig"] = None
        self._ports: Optional["SystemPorts"] = None

        self._lock = RLock()
        self.sessions: Dict["TradingSessionKey", "TradingSession"] = {}
        self._order_router: Optional["GlobalOrderRouter"] = None

    def configure(self, *, config: "SessionConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("SessionManager: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def init_order_router(self, *, sink) -> None:
        if sink is None:
            raise ValueError("SessionManager: init_order_router() requires a non-null sink")
        if self._order_router is not None:
            raise RuntimeError("SessionManager: router already initialized")

        self._order_router = GlobalOrderRouter(sink=sink)

    @property
    def router(self) -> "GlobalOrderRouter":
        if self._order_router is None:
            raise RuntimeError(
                "SessionManager: router not initialized yet. "
                "Call init_order_router(sink=...) after IBKR sink injection."
            )
        return self._order_router

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> "SessionConfig":
        if self._config is None:
            raise RuntimeError("SessionManager: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("SessionManager: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

# -------- API ----------------------

    def _current_session_date(self):
        # TODO:HIGH Persist current day dans un format ISO (ou équivalent)
        return self.ports.market_calendar.today()

    def _build_session_key(
        self,
        session_cfg: "TradingSessionConfig",
        portfolio_cfg: "PortfolioConfig"
    ) -> "TradingSessionKey":
        return TradingSessionKey(
            session_date=self._current_session_date(),
            account_id=session_cfg.account_id,
            portfolio_id=portfolio_cfg.portfolio_id,
            mode=session_cfg.mode,
        )

    def _create_trading_session(
        self,
        session_cfg: "TradingSessionConfig",
        portfolio_cfg: "PortfolioConfig",
        payload: dict | None = None
    ) -> "TradingSession":
        key = self._build_session_key(session_cfg=session_cfg, portfolio_cfg=portfolio_cfg)
        return TradingSession(
            key=key,
            payload=payload,
            ports=self.ports,
            router=self.router
        )

    def initialize_sessions_from_config(self) -> None:
        for session_cfg in getattr(self._config, "sessions", []):
            for portfolio_cfg in session_cfg.portfolios:
                if getattr(portfolio_cfg, "enabled", True) is False:
                    continue

                session = self._create_trading_session(
                    session_cfg=session_cfg,
                    portfolio_cfg=portfolio_cfg
                )

                if session.key in self.sessions:
                    continue

                self.sessions[session.key] = session
                session.initialize_modules()

                result = session.health_check()
                if result.get("is_healthy") is False:
                    raise HealthCheckError(result)

            # TODO:MEDIUM if session failed and session.mode == "PAPER", then erase session

    def load_sessions_state_from_database(self) -> None:
        for session in self.sessions.values():
            session.stack.portfolio.load_portfolio_state()


    def load_sessions_portfolio_orders(self) -> None:
        for session in self.sessions.values():
            session.stack.portfolio.load_portfolio_orders()


    def health_check_loaded_sessions(self) -> None:

        results: list[dict[str, Any]] = []

        for key, session in self.sessions.items():
            portfolio_result = session.stack.portfolio.health_check()
            results.append(portfolio_result)

            risk_result = session.stack.risk.health_check()
            results.append(risk_result)

        failures = [r for r in results if r.get("is_healthy") is False]
        if failures:
            raise HealthCheckError(failures)

        # TODO:MEDIUM if session failed and session.mode == "PAPER", then erase session with a new fonction







    # region OldFunction

    def get_session(self, key: "TradingSessionKey") -> "TradingSession":
        with self._lock:
            if key not in self.sessions:
                raise KeyError(f"TradingSession inconnue: {key}")
            return self.sessions[key]

    def start_session(self, key: "TradingSessionKey") -> None:
        session = self.get_session(key)
        session.start()

    def stop_session(self, key: "TradingSessionKey") -> None:
        session = self.get_session(key)
        session.stop()

    def list_sessions(self) -> tuple["TradingSessionKey", ...]:
        with self._lock:
            return tuple(self.sessions.values())


        # On crée un objet compatible "MarketDaySession" côté système plus tard.
        # Ici on passe un objet duck-typed minimal attendu par DIL.
        class _MarketDaySessionLike:
            def __init__(self, session_date: date, payload: Dict[str, Any]) -> None:
                self.session_date = session_date
                self.payload = payload

        obj = _MarketDaySessionLike(session_date=session_date, payload=payload)

        if self._data_ingestion.exists_for_date(session_date):
            self._data_ingestion.update(obj)
        else:
            self._data_ingestion.insert(obj)

    # endregion





_instance: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    global _instance
    if _instance is None:
        _instance = SessionManager()
    return _instance