from __future__ import annotations

from typing import Any, Protocol


class LogService(Protocol):
    def info(self, message: str, **fields: Any) -> None: ...
    def error(self, message: str, **fields: Any) -> None: ...


class NullLogService:
    def info(self, message: str, **fields: Any) -> None:
        return

    def error(self, message: str, **fields: Any) -> None:
        return
