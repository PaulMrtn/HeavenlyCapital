from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING
from uuid import UUID

from heavenly_capital.models.portfolio import PortfolioSnapshot, Portfolio

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey


class PortfolioManager:
    def __init__(self) -> None:
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._state: Optional["Portfolio"] = None

        self._configured = False
        self._started = False

    def configure(self, *, session_id: UUID, key: "TradingSessionKey", ports: "SystemPorts") -> None:
        self._key = key
        self._session_id = session_id
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("PortfolioManager: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def authorize_order(self, order_intent: Dict[str, Any]) -> bool: ...

    def load_portfolio_state(self) -> None:
        if not self._configured:
            raise RuntimeError("PortfolioManager: bootstrap_portfolio_state() called before configure()")

        snapshot: PortfolioSnapshot = self._ports.data_access.get_portfolio_snapshot(self._key.account_id)
        self._state = Portfolio.from_snapshot(snapshot)


    @property
    def portfolio_state(self) -> Optional[PortfolioSnapshot]:
        return self._state

    # TODO:MEDIUM : add property for each attribut like inventories, etc

    def refresh_portfolio_state(self) -> None: ...

    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }





