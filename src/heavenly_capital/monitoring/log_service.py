from __future__ import annotations

from typing import Any, Protocol


class LogService(Protocol):
    def info(self, message: str, **fields: Any) -> None: ...
    def error(self, message: str, **fields: Any) -> None: ...


class NullLogService:

    def info(self, message: str, **fields: Any) -> None:
        if fields:
            print(f"[INFO] {message} | {fields}")
        else:
            print(f"[INFO] {message}")

    def error(self, message: str, **fields: Any) -> None:
        if fields:
            print(f"[ERROR] {message} | {fields}")
        else:
            print(f"[ERROR] {message}")