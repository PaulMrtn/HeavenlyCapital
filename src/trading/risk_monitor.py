from __future__ import annotations

from typing import Dict, Any, Optional, TYPE_CHECKING
from uuid import UUID

from src.models.risk import RiskSnapshot


if TYPE_CHECKING:
    from src.core.system_manager import SystemPorts
    from src.core.session_manager import TradingSessionKey


class RiskMonitor:
    def __init__(self) -> None:
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._state: Optional[RiskSnapshot] = None

        self._configured = False
        self._started = False

    def configure(self, *, session_id: UUID, key: "TradingSessionKey", ports: "SystemPorts") -> None:
        self._key = key
        self._session_id = session_id
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("RiskMonitor: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False


    def authorize_order(self, order_intent: Dict[str, Any]) -> bool: ...


    def refresh_risk_state(self) -> None:
        if not self._configured:
            raise RuntimeError("PortfolioManager: refresh_portfolio_state() called before configure()")

        snapshot = self._ports.data_access.get_risk_snapshot(self._key.account_id)
        self._state = snapshot

    @property
    def risk_state(self) -> Optional[RiskSnapshot]:
        return self._state
