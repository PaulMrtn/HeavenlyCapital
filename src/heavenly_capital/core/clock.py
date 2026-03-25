# core/clock.py

from __future__ import annotations

import threading
from enum import Enum, auto
import time
from dataclasses import dataclass



class MarketState(Enum):
    CLOSED = auto()
    PRE_MARKET = auto()
    OPEN = auto()
    POST_MARKET = auto()

class TradingState(Enum):
    READ_ONLY = auto()
    STOP = auto()
    EXECUTION = auto()
    CLOSED = auto()

@dataclass(frozen=True)
class TradingStateChangeEvent:
    previous: TradingState
    current: TradingState
    timestamp: float

@dataclass(frozen=True)
class MarketStateChangeEvent:
    previous: MarketState
    current: MarketState
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
        self._trading_state = TradingState.CLOSED
        self._step_state = 0

        self._market_subscribers = []
        self._trading_subscribers = []

        self._initialized = True

        self._time_source = time_source
        self._time_source.subscribe(self.on_heartbeat)


    def subscribe_market(self, callback):
        self._market_subscribers.append(callback)

    def subscribe_trading(self, callback):
        self._trading_subscribers.append(callback)


    @staticmethod
    def _compute_market_state(timestamp: float) -> MarketState:
        local_time = time.localtime(timestamp)
        hour_decimal = local_time.tm_hour + local_time.tm_min / 60

        if 4 <= hour_decimal < 9.5:
            return MarketState.PRE_MARKET
        if 9.5 <= hour_decimal < 16:
            return MarketState.OPEN
        if 16 <= hour_decimal < 20:
            return MarketState.POST_MARKET
        return MarketState.CLOSED

    @staticmethod
    def _compute_trading_state(timestamp: float) -> TradingState:
        local_time = time.localtime(timestamp)
        hour_decimal = local_time.tm_hour + local_time.tm_min / 60

        if (4 <= hour_decimal < 8) or (18 <= hour_decimal < 20):
            return TradingState.READ_ONLY
        if (6.5 <= hour_decimal < 9.5) or (16 <= hour_decimal < 18):
            return TradingState.STOP
        if 9.5 <= hour_decimal < 16:
            return TradingState.EXECUTION
        return TradingState.CLOSED

    @staticmethod
    def _compute_step_state(timestamp: float) -> int:
        local_time = time.localtime(timestamp)

        minutes_since_midnight = local_time.tm_hour * 60 + local_time.tm_min

        start = 9 * 60 + 30
        end = 16 * 60

        if minutes_since_midnight < start:
            return 0

        if minutes_since_midnight >= end:
            return 390

        return minutes_since_midnight - start


    def on_heartbeat(self, timestamp: float):
        self._step_state = self._compute_step_state(timestamp)

        new_market_state = self._compute_market_state(timestamp)
        new_trading_state = self._compute_trading_state(timestamp)

        if new_market_state != self._market_state:
            event_market = MarketStateChangeEvent(
                previous=self._market_state,
                current=new_market_state,
                timestamp=timestamp
            )
            self._market_state = new_market_state
            self._notify_market(event_market)

        if new_trading_state != self._trading_state:
            event_trading = TradingStateChangeEvent(
                previous=self._trading_state,
                current=new_trading_state,
                timestamp=timestamp
            )
            self._trading_state = new_trading_state
            self._notify_trading(event_trading)


    def _notify_market(self, event: MarketStateChangeEvent):
        for cb in self._market_subscribers:
            cb(event)

    def _notify_trading(self, event: TradingStateChangeEvent):
        for cb in self._trading_subscribers:
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
        return self._trading_state == TradingState.EXECUTION

    @property
    def is_trading_stopped(self) -> bool:
        return self._trading_state == TradingState.STOP

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
