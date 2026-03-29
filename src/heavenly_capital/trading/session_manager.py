from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING
from uuid import uuid4, UUID

from ib_async import Contract

from heavenly_capital.data.bus import EventBus
from heavenly_capital.models.config import SessionConfig
from heavenly_capital.models.runtime import RuntimeModule
from heavenly_capital.models.market_data import TickerManager
from heavenly_capital.models.trading_engine import TradingSessionKey, TradingEngine
from heavenly_capital.monitoring.error_service import HealthCheckError
from heavenly_capital.trading.router import GlobalOrderRouter

from heavenly_capital.models.session import TradingSessionConfig, PortfolioConfig

from heavenly_capital.trading.order_manager import OrderManager
from heavenly_capital.trading.portfolio_manager import PortfolioManager
from heavenly_capital.trading.risk_manager import RiskManager


if TYPE_CHECKING:
    from heavenly_capital.core.kernel import SystemPorts




class TradingSession:
    def __init__(
        self,
        key: "TradingSessionKey",
        router: "GlobalOrderRouter",
        ports: "SystemPorts",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:

        self.key = key
        self.session_id: UUID = uuid4()

        self._payload: Dict[str, Any] = payload or {}
        self._ports: "SystemPorts" = ports
        self._order_router: "GlobalOrderRouter" = router

        self.stack: Optional["TradingEngine"] = None

    @property
    def ports(self) -> "SystemPorts":
        return self._ports

    @property
    def router(self) -> "GlobalOrderRouter":
        return self._order_router

    @property
    def engine(self) -> "TradingEngine":
        if self.stack is None:
            raise RuntimeError("TradingSession engine not initialized")
        return self.stack

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


    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }


    def load_contracts(self, contracts: dict[str, "Contract"]) -> None:
        self.engine.orders.load_contracts(contracts)

    def wire_live_tickers(self, ticker_manager: "TickerManager") -> None:
        self.engine.portfolio.wire_ticker_manager(ticker_manager)
        self.engine.risk.wire_ticker_manager(ticker_manager)

    def wire_forecast_signal(self, bus: "EventBus"):
        self.engine.portfolio.wire_forecast_manager(bus)
        # self.engine.risk.wire_forecast_manager(bus)




class SessionManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional["SessionConfig"] = None
        self._ports: Optional["SystemPorts"] = None

        self.sessions: Dict["TradingSessionKey", "TradingSession"] = {}
        self._order_router: Optional["GlobalOrderRouter"] = None

    def configure(self, config: "SessionConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("SessionManager: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def wire_order_router(self, *, sink) -> None:
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


    def _current_session_date(self):
        return self.ports.market_calendar.today()

    def load_session_configs(self) -> tuple["TradingSessionConfig", ...]:
        rows = self._ports.db_service.reader.fetch_trading_sessions()
        return tuple(
            TradingSessionConfig.from_database(row)
            for row in rows
        )

    def initialize_sessions_from_config(self) -> None:
        # TODO:LOW split this fn into multiple ones
        # load_session_configs()
        # create_sessions()
        # initialize_sessions()
        # validate_sessions()

        if not self._configured :
            return

        if self._order_router is None:
            raise RuntimeError("Order router must be wired before creating sessions")

        for session_cfg in self.load_session_configs():
            for portfolio_cfg in session_cfg.portfolios:
                if getattr(portfolio_cfg, "enabled", True) is False:
                    continue

                session = self._create_trading_session(
                    session_cfg=session_cfg,
                    portfolio_cfg=portfolio_cfg
                )

                if session.key in self.sessions:
                    continue

                session.initialize_modules()
                self.sessions[session.key] = session

                result = session.health_check()
                if result.get("is_healthy") is False:
                    raise HealthCheckError(result)

            # TODO:MEDIUM if session failed and session.mode == "PAPER", then erase session


    def _create_trading_session(
        self,
        session_cfg: "TradingSessionConfig",
        portfolio_cfg: "PortfolioConfig",
        payload: Optional[Dict[str, Any]] = None
    ) -> "TradingSession":
        key = self._build_session_key(session_cfg=session_cfg, portfolio_cfg=portfolio_cfg)
        return TradingSession(
            key=key,
            payload=payload,
            ports=self.ports,
            router=self.router
        )

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

    def load_sessions_state_from_database(self) -> None:
        for session in self.sessions.values():
            session.engine.portfolio.load_portfolio_state()


    def load_sessions_portfolio_orders(self) -> None:
        for session in self.sessions.values():
            session.engine.portfolio.load_portfolio_orders()


    def health_check_loaded_sessions(self) -> None:
        results: list[dict[str, Any]] = []

        for key, session in self.sessions.items():
            portfolio_result = session.engine.portfolio.health_check()
            results.append(portfolio_result)

            risk_result = session.engine.risk.health_check()
            results.append(risk_result)

        failures = [r for r in results if r.get("is_healthy") is False]
        if failures:
            raise HealthCheckError(failures)

        # TODO:MEDIUM if session failed and session.mode == "PAPER", then erase session with a new fonction




_instance: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    global _instance
    if _instance is None:
        _instance = SessionManager()
    return _instance




# Gestion des erreurs de santé (health_check) :
# Dans initialize_sessions_from_config, tu lances une HealthCheckError dès qu'une session échoue. Cela arrête tout le gestionnaire.
# Critique : Si tu as 10 sessions et qu'une seule échoue (ex: erreur de config sur un compte papier), est-il souhaitable de bloquer
# le démarrage des 9 autres ? Une approche par "quarantaine" serait plus résiliente.

# UUID vs Key : Tu génères un self.session_id (UUID), mais tu stockes les sessions par self.key (TradingSessionKey).
# C'est très bien pour l'idempotence (éviter les doublons de sessions pour un même compte le même jour).