from __future__ import annotations

from typing import Dict, Any, Optional, TYPE_CHECKING
from uuid import UUID

from heavenly_capital.core.runtime_config import BaseModule, ModuleType
from heavenly_capital.models.risk import RiskSnapshot, RiskState

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey


class RiskMonitor(BaseModule):
    def __init__(self) -> None:
        super().__init__()
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._state: Optional["RiskState"] = None
        self._market_state = None

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

    def dispatch(self, target: ModuleType, action: str, data: Any) -> None:
        payload = {
            "action": action,
            "data": data
        }
        self.send(target, payload)

    def authorize_order(self, con_id: int) -> None:
        auth_payload = {
            "con_id": con_id,
            "authorized":True
        }

        self.dispatch(ModuleType.ORDERS, "authorize_order", auth_payload)

    def load_risk_state(self) -> None:
        if not self._configured:
            raise RuntimeError("RiskMonitor: bootstrap_risk_state() called before configure()")

        snapshot = self._ports.data_access.get_risk_snapshot(self._key.account_id)
        self._state = RiskState.from_snapshot(snapshot)

    @property
    def risk_state(self) -> Optional[RiskSnapshot]:
        return self._state

    # TODO:MEDIUM : add property for each attribut like stop_loss, etc

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }

    def wire_market_state(self, market_state):
        self._market_state = market_state
