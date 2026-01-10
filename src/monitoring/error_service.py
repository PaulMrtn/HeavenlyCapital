from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class ErrorEvent:
    kind: str  # ex: "DATA", "TRADING", "INFRA", ...
    message: str
    exception_type: Optional[str] = None
    context: dict[str, Any] | None = None


class ErrorService(Protocol):
    def capture(self, error: Exception, **context: Any) -> None: ...
    def report(self, event: ErrorEvent) -> None: ...


class NullErrorService:
    def capture(self, error: Exception, **context: Any) -> None:
        return

    def report(self, event: ErrorEvent) -> None:
        return