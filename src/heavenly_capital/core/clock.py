# core/clock.py

from __future__ import annotations

import threading
from enum import Enum, auto
import time
from dataclasses import dataclass
from typing import Optional


class MarketState(Enum):
    CLOSED = auto()
    PRE_MARKET = auto()
    OPEN = auto()
    POST_MARKET = auto()

class TradingState(Enum):
    READ_ONLY = auto()
    RISK_ONLY = auto()
    EXECUTION_ENABLED = auto()
    EXECUTION_DISABLED = auto()

class MarketSessionPhase(Enum):
    INITIALIZATION = auto()
    STAND_BY = auto()
    RUNNING = auto()
    SETTLING = auto()
    SHUTDOWN = auto()

@dataclass(frozen=True)
class TradingChangeState:
    previous: TradingState
    current: TradingState
    timestamp: float

@dataclass(frozen=True)
class MarketEventChangeEvent:
    previous: MarketState
    current: MarketState
    timestamp: float

@dataclass(frozen=True)
class MarketSessionPhaseChangeEvent:
    previous: MarketSessionPhase
    current: Optional[MarketSessionPhase]
    timestamp: float


class SystemTimeHeartbeat:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, tick_seconds: float = 1.0):
        if self._initialized:
            return
        self._tick_seconds = tick_seconds
        self._subscribers = []
        self._running = False
        self._initialized = True

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def _run(self):
        while self._running:
            now = time.time()
            for cb in self._subscribers:
                cb(now)
            time.sleep(self._tick_seconds)

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False


class MarketClock:
    # TODO: WARNING — Refactor state transitions (market/trading/system):
    #  remove duplicated logic, factorize transition handling, and simplify on_heartbeat().

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, time_source):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, time_source):
        if self._initialized:
            return
        self._market_state = MarketState.CLOSED
        self._trading_state = TradingState.EXECUTION_DISABLED
        self._system_state = MarketSessionPhase.INITIALIZATION
        self._step_state = 0

        self._system_subscribers = []
        self._market_subscribers = []
        self._trading_subscribers = []

        self._initialized = True

        self._time_source = time_source
        self._time_source.subscribe(self.on_heartbeat)


    def subscribe_market(self, callback):
        self._market_subscribers.append(callback)

    def subscribe_trading(self, callback):
        self._trading_subscribers.append(callback)

    def subscribe_kernel(self, callback):
        self._system_subscribers.append(callback)


    @staticmethod
    def _compute_market_state(timestamp: float) -> MarketState:
        lt = time.localtime(timestamp)
        t = lt.tm_hour + lt.tm_min / 60

        if 4 <= t < 9.5:
            return MarketState.PRE_MARKET
        if 9.5 <= t < 16:
            return MarketState.OPEN
        if 16 <= t < 20:
            return MarketState.POST_MARKET
        return MarketState.CLOSED

    @staticmethod
    def _compute_trading_state(timestamp: float) -> TradingState:
        lt = time.localtime(timestamp)
        t = lt.tm_hour + lt.tm_min / 60

        if 4 <= t < 6.5 or 18 <= t < 20:
            return TradingState.READ_ONLY
        elif 6.5 <= t < 9.5 or 16 <= t < 18:
            return TradingState.RISK_ONLY
        elif 9.5 <= t < 16:
            return TradingState.EXECUTION_ENABLED
        else:
            return TradingState.EXECUTION_DISABLED


    @staticmethod
    def _compute_system_event(timestamp: float) -> Optional[MarketSessionPhase]:
        lt = time.localtime(timestamp)
        t = lt.tm_hour + lt.tm_min / 60

        if 4 <= t < 20:
            return MarketSessionPhase.RUNNING

        return None


    @staticmethod
    def _compute_step_state(timestamp: float) -> int:
        lt = time.localtime(timestamp)
        t = lt.tm_hour * 60 + lt.tm_min

        start = 9 * 60 + 30
        end = 16 * 60

        if t < start:
            return 0

        if t >= end:
            return 390

        return t - start


    def on_heartbeat(self, timestamp: float):
        self._step_state = self._compute_step_state(timestamp)

        new_market_state = self._compute_market_state(timestamp)
        new_trading_state = self._compute_trading_state(timestamp)
        _new_system_state = self._compute_system_event(timestamp)

        if new_market_state != self._market_state:
            event_market = MarketEventChangeEvent(
                previous=self._market_state,
                current=new_market_state,
                timestamp=timestamp
            )
            self._market_state = new_market_state
            self._notify_market(event_market)


        if new_trading_state != self._trading_state:
            event_trading = TradingChangeState(
                previous=self._trading_state,
                current=new_trading_state,
                timestamp=timestamp
            )
            self._trading_state = new_trading_state
            self._notify_trading(event_trading)


        if _new_system_state != self._system_state:
            event_kernel = MarketSessionPhaseChangeEvent(
                previous=self._system_state,
                current=_new_system_state,
                timestamp=timestamp
            )
            self._system_state = _new_system_state
            self._notify_kernel(event_kernel)



    def _notify_market(self, event: MarketEventChangeEvent):
        for cb in self._market_subscribers:
            cb(event)

    def _notify_trading(self, event: TradingChangeState):
        for cb in self._trading_subscribers:
            cb(event)

    def _notify_kernel(self, event: MarketSessionPhaseChangeEvent):
        for cb in self._system_subscribers:
            cb(event)





    def start(self):
        self._time_source.start()

    def stop(self):
        self._time_source.stop()


    @property
    def step_state(self) -> int:
        return self._step_state

    @property
    def is_execution_time(self) -> bool:
        return self._trading_state == TradingState.EXECUTION_ENABLED

    @property
    def is_trading_stopped(self) -> bool:
        return self._trading_state == TradingState.RISK_ONLY

    @property
    def is_read_only(self) -> bool:
        return self._trading_state == TradingState.READ_ONLY

    @property
    def is_market_open(self) -> bool:
        return self._market_state == MarketState.OPEN

    @property
    def is_pre_market(self) -> bool:
        return self._market_state == MarketState.PRE_MARKET

    @property
    def is_post_market(self) -> bool:
        return self._market_state == MarketState.POST_MARKET





class AcceleratedTimeHeartbeat:
    def __init__(
        self,
        day_seconds: float = 10.0,
        tick_seconds: float = 0.05,
        start_timestamp: float | None = None,
    ):
        if day_seconds <= 0:
            raise ValueError("day_seconds doit être > 0")
        if tick_seconds <= 0:
            raise ValueError("tick_seconds doit être > 0")

        self._day_seconds = float(day_seconds)
        self._tick_seconds = float(tick_seconds)
        self._subscribers: list = []
        self._running = False

        self._real_t0 = None
        self._sim_t0 = time.time() if start_timestamp is None else float(start_timestamp)

        self._speed = 86400.0 / self._day_seconds

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def start(self):
        if self._running:
            return
        self._running = True
        self._real_t0 = time.time()
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            real_elapsed = time.time() - self._real_t0
            sim_now = self._sim_t0 + real_elapsed * self._speed

            for cb in list(self._subscribers):
                cb(sim_now)

            time.sleep(self._tick_seconds)
