from __future__ import annotations

import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Protocol


class MetricService(Protocol):

    def __init__(self, *args, **kwargs):
        self._histograms: dict[str, deque[float]] = {}

    def incr(self, name: str, value: int = 1, **tags: Any) -> None: ...


    def timing(self, key: str, value_ms: float) -> None:
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = deque(maxlen=100)
            self._histograms[key].append(value_ms)

    @contextmanager
    def timer(self, key: str):
        start = time.perf_counter()

        try:
            yield

        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self.timing(key, elapsed)



class NullMetricService:
    def incr(self, name: str, value: int = 1, **tags: Any) -> None:
        return
