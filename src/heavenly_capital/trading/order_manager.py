from __future__ import annotations

from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from uuid import UUID

from heavenly_capital.models.order import OrderRequest
from heavenly_capital.models.order import OrderTracker

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey, GlobalOrderRouter

OrderPolicy = Callable[[Dict[str, Any]], bool]



class OrderManager:
    def __init__(self) -> None:
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._router: Optional["GlobalOrderRouter"] = None

        self._portfolio_authorizer: Optional[OrderPolicy] = None
        self._risk_authorizer: Optional[OrderPolicy] = None

        self._configured = False
        self._started = False

    def configure(self, *, session_id: UUID, key: "TradingSessionKey", ports: "SystemPorts") -> None:
        self._key = key
        self._session_id = session_id
        self._ports = ports
        self._configured = True

    def wire(
        self,
        *,
        portfolio_authorizer: OrderPolicy,
        risk_authorizer: OrderPolicy,
    ) -> None:
        self._portfolio_authorizer = portfolio_authorizer
        self._risk_authorizer = risk_authorizer

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("OrderManager: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def set_router(self, router: "GlobalOrderRouter") -> None:
        self._router = router

    def route_order(self, order: "OrderTracker") -> None:
        if self._router is None:
            raise RuntimeError("OrderManager: router non configuré (set_router() non appelé)")
        if self._key is None:
            raise RuntimeError("OrderManager: key non configurée (configure() non appelé)")

        self._router.route_order(session_key=self._key, order=order)


    def _build_contract(self): ...


