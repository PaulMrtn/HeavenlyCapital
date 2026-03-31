from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock, Condition
from typing import Callable, Deque, Optional, TYPE_CHECKING

from heavenly_capital.core.thread import get_thread_manager

if TYPE_CHECKING:
    from threading import Event
    from heavenly_capital.trading.session_manager import TradingSessionKey
    from heavenly_capital.models.order import OrderTracker


@dataclass(frozen=True)
class RoutedOrder:
    seq: int
    session_key: "TradingSessionKey"
    order: "OrderTracker"


class GlobalOrderRouter:
    def __init__(
            self,
            *,
            sink: Callable[["TradingSessionKey", "OrderTracker"], None] | None,
            name: str = "order_router" #TODO:LOW erase this name attribut
    ) -> None:
        self._sink = sink
        self._name = name

        self._lock = RLock()
        self._cv = Condition(self._lock)

        self._seq = 0
        self._live: Deque[RoutedOrder] = deque()
        self._paper: Deque[RoutedOrder] = deque()

        self._register_thread()

    def _register_thread(self) -> None:
        tm = get_thread_manager()
        tm.register_thread(
            name=self._name,
            target=self._order_router_loop,
            daemon=True
        )

    def route_order(self, *, session_key: "TradingSessionKey", order: "OrderTracker") -> None:
        with self._cv:
            self._seq += 1
            ro = RoutedOrder(seq=self._seq, session_key=session_key, order=order)

            if session_key.mode == "LIVE":
                self._live.append(ro)
            else:
                self._paper.append(ro)

            self._cv.notify_all()

    def _pop_next(self) -> Optional[RoutedOrder]:
        if self._live:
            return self._live.popleft()
        if self._paper:
            return self._paper.popleft()
        return None

    def pending_count(self) -> int:
        with self._lock:
            return len(self._live) + len(self._paper)

    def _order_router_loop(self, stop_event: "Event") -> None:
        while not stop_event.is_set() or self.pending_count() > 0:

            with self._cv:
                while not self._live and not self._paper:
                    if stop_event.is_set():
                        return
                    self._cv.wait(timeout=0.5)

                routed_order = self._pop_next()

            if routed_order:
                try:
                    if self._sink:
                        self._sink(routed_order.session_key, routed_order.order)
                except Exception as e:
                    print(f"[{self._name}] Error while routing order: {e}")
