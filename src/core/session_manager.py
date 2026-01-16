from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from datetime import date, datetime
from enum import Enum
from threading import Condition, RLock, Thread
from typing import Any, Callable, Deque, Dict, Optional, Tuple, TYPE_CHECKING
from uuid import uuid4, UUID

from src.core.runtime_config import SessionConfig
from src.core.system_manager import RuntimeModule

if TYPE_CHECKING:
    from src.core.system_manager import SystemPorts


class TradingMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class SessionState(str, Enum):
    NEW = "NEW"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class TradingSessionKey:
    session_date: date
    account_id: str
    strategy_id: str
    mode: TradingMode


@dataclass
class MarketDaySessionSnapshot:
    session_date: date
    account_id: str
    strategy_id: str
    mode: str
    state: str
    created_at_utc: str
    updated_at_utc: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class RoutedOrder:
    seq: int
    session_key: TradingSessionKey
    order: Dict[str, Any] # TODO : replace by OrderObject


class GlobalOrderRouter:

    def __init__(
            self,
            *,
            sink: Callable[[TradingSessionKey, Dict[str, Any]], None] | None,
            start_worker: bool = True,
            name: str = "global-order-router",
    ) -> None:
        self._sink = sink

        self._lock = RLock()
        self._cv = Condition(self._lock)

        self._seq = 0
        self._live: Deque[RoutedOrder] = deque()
        self._paper: Deque[RoutedOrder] = deque()

        self._closed = False
        self._worker: Optional[Thread] = None

        if start_worker:
            self._worker = Thread(target=self._run, name=name, daemon=True)
            self._worker.start()

    def close(self) -> None:

        with self._cv:
            self._closed = True
            self._cv.notify_all()

        if self._worker is not None:
            # TODO:HIGH : add .join() to threadPool
            self._worker.join()

    def route_order(self, *, session_key: TradingSessionKey, order: Dict[str, Any]) -> None:
        # TODO: créer un objet Order contenant toutes les infos de TradingSessionKey et supprimer session-key en input.

        with self._cv:
            if self._closed:
                return

            self._seq += 1
            ro = RoutedOrder(seq=self._seq, session_key=session_key, order=order)

            if session_key.mode == TradingMode.LIVE:
                self._live.append(ro)
            else:
                self._paper.append(ro)

            self._cv.notify()

    def _pop_next(self) -> Optional[RoutedOrder]:

        with self._lock:
            if self._live:
                return self._live.popleft()
            if self._paper:
                return self._paper.popleft()
            return None

    def _run(self) -> None:

        while True:
            with self._cv:
                while not self._closed and not self._live and not self._paper:
                    self._cv.wait()

                if self._closed and not self._live and not self._paper:
                    return

            routed_order = self._pop_next()
            if routed_order is None:
                continue

            try:
                self._sink(routed_order.session_key, routed_order.order)
            except Exception as e:
                print(f"Error while routing order : {e}")


    def pending_count(self) -> int:
        with self._lock:
            return len(self._live) + len(self._paper)


class TradingSession:
    def __init__(self, *, key: TradingSessionKey, payload: Optional[Dict[str, Any]] = None) -> None:
        self.key = key
        self.session_id: UUID = uuid4()
        self.state = SessionState.NEW
        self._payload: Dict[str, Any] = payload or {}


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

    def snapshot(self) -> MarketDaySessionSnapshot:
        return MarketDaySessionSnapshot(
            session_date=self.key.session_date,
            account_id=self.key.account_id,
            strategy_id=self.key.strategy_id,
            mode=self.key.mode.value,
            state=self.state.value,
            payload=dict(self._payload),
        )




class SessionManager(RuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional[SessionConfig] = None
        self._ports: Optional["SystemPorts"] = None

        self._lock = RLock()
        self._sessions: Dict[TradingSessionKey, TradingSession] = {}
        self._router: Optional[GlobalOrderRouter] = None

    def configure(self, *, config: SessionConfig, ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("SessionManager: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def init_router(self, *, sink) -> None:
        if sink is None:
            raise ValueError("SessionManager: init_router() requires a non-null sink")
        if self._router is not None:
            raise RuntimeError("SessionManager: router already initialized")
        self._router = GlobalOrderRouter(sink=sink)

    @property
    def router(self) -> GlobalOrderRouter:
        if self._router is None:
            raise RuntimeError(
                "SessionManager: router not initialized yet. "
                "Call init_router(sink=...) after IBKR sink injection."
            )
        return self._router

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> SessionConfig:
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
        # TODO:HIGH Persist current day dans unf format ISO (ou équivalent)
        return self.ports.market_calendar.today()

    def _build_session_key(self, *, session_cfg) -> TradingSessionKey:
        return TradingSessionKey(
            session_date=self._current_session_date(),
            account_id=session_cfg.account_id,
            strategy_id=session_cfg.strategy_id,
            mode=session_cfg.mode,
        )

    def _create_trading_session(self, *, session_cfg, payload: dict | None = None) -> TradingSession:
        key = self._build_session_key(session_cfg=session_cfg)
        return TradingSession(key=key, payload=payload)

    def _init_sessions_from_config(self) -> None:
        for session_cfg in getattr(self._config, "sessions", []):
            session = self._create_trading_session(session_cfg=session_cfg)

            if session.key in self._sessions:
                continue

            self._sessions[session.key] = session







# region OldFunction

    def get_session(self, key: TradingSessionKey) -> TradingSession:
        with self._lock:
            if key not in self._sessions:
                raise KeyError(f"TradingSession inconnue: {key}")
            return self._sessions[key]

    def start_session(self, key: TradingSessionKey) -> None:
        session = self.get_session(key)
        session.start()

    def stop_session(self, key: TradingSessionKey) -> None:
        session = self.get_session(key)
        session.stop()

    def list_sessions(self) -> Tuple[TradingSession, ...]:
        with self._lock:
            return tuple(self._sessions.values())


    def end_of_day_persist(self) -> None:
        """
        Persiste toutes les sessions de la journée (snapshot).
        On s'appuie sur DataIngestionLayer: insert/update/exists_for_date,
        donc à ce stade on persiste "par date" (version minimaliste).
        """
        with self._lock:
            sessions = list(self._sessions.values())

        # Remarque: ton DIL actuel est indexé par date uniquement;
        # donc pour supporter plusieurs sessions par date, il faudra évoluer le storage.
        # Pour démarrer, on stocke une structure agrégée par date.
        if not sessions:
            return

        session_date = sessions[0].key.session_date
        payload = {
            "sessions": [asdict(s.snapshot()) for s in sessions],
        }

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