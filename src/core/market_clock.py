# core/market_clock.py

from __future__ import annotations

import threading
from abc import ABC, abstractmethod, ABCMeta
from enum import Enum, auto
import time
from dataclasses import dataclass



class MarketState(Enum):
    CLOSED = auto()
    PRE_MARKET = auto()
    OPEN = auto()
    POST_MARKET = auto()

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

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, time_source):
        if self._initialized:
            return
        self._market_state = MarketState.CLOSED
        self._subscribers = []
        self._initialized = True

        self._time_source = time_source
        self._time_source.subscribe(self.on_heartbeat)

    def subscribe(self, callback):
        self._subscribers.append(callback)

    @staticmethod
    def _compute_market_state(timestamp: float) -> MarketState:
        local_time = time.localtime(timestamp)
        hour = local_time.tm_hour

        if 8 <= hour < 9:
            return MarketState.PRE_MARKET
        if 9 <= hour < 16:
            return MarketState.OPEN
        if 16 <= hour < 18:
            return MarketState.POST_MARKET
        return MarketState.CLOSED

    def on_heartbeat(self, timestamp: float):
        new_state = self._compute_market_state(timestamp)

        if new_state != self._market_state:
            event = MarketStateChangeEvent(
                previous=self._market_state,
                current=new_state,
                timestamp=timestamp
            )
            self._market_state = new_state
            self._notify(event)

    def _notify(self, event):
        for cb in self._subscribers:
            cb(event)

    def start(self):
        self._time_source.start()

    def stop(self):
        self._time_source.stop()


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
