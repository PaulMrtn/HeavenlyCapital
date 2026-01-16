from __future__ import annotations

from typing import Dict, Any
from uuid import UUID

class RiskMonitor:
    def __init__(self) -> None:
        self._configured = False
        self._started = False

    def configure(self, *, session_id: UUID, payload: Dict[str, Any]) -> None:
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("RiskMonitor: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False
