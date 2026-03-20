from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock, Condition, Thread
from typing import Callable, Deque, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from heavenly_capital.core.session_manager import TradingSessionKey, TradingMode
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

    def route_order(self, *, session_key: TradingSessionKey, order: "OrderTracker") -> None:
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

    def _pop_next(self) -> Optional["RoutedOrder"]:

        with self._lock:
            if self._live:
                return self._live.popleft()
            if self._paper:
                return self._paper.popleft()
            return None

    def _run(self) -> None:
        #TODO:LOW - Rename this thread function
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