from __future__ import annotations

from typing import Any, Protocol


class MetricService(Protocol):
    def incr(self, name: str, value: int = 1, **tags: Any) -> None: ...


class NullMetricService:
    def incr(self, name: str, value: int = 1, **tags: Any) -> None:
        return
