from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol


Priority = Literal["low", "normal", "high", "critical"]


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    priority: Priority = "normal"
    channel: Optional[str] = None  # ex: "ops", "trading", ...
    context: dict[str, Any] | None = None


class NotificationService(Protocol):
    def notify(self, notification: Notification) -> None: ...


class NullNotificationService:
    def notify(self, notification: Notification) -> None:
        return