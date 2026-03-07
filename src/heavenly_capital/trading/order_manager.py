from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING, Callable
from uuid import UUID

from ib_async import Contract

from heavenly_capital.core.runtime_config import BaseModule, ModuleType
from heavenly_capital.models.order import OrderTracker, OrderRequest

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey, GlobalOrderRouter


class OrderManager(BaseModule):
    def __init__(self) -> None:

        super().__init__()
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._order_router: Optional["GlobalOrderRouter"] = None

        self._contracts: dict[int, Contract] = {}
        self._pending_orders: Dict[int, OrderTracker] = {}

        self._configured = False
        self._started = False


    def configure(self, *, session_id: UUID, key: "TradingSessionKey", ports: "SystemPorts") -> None:
        self._key = key
        self._session_id = session_id
        self._ports = ports
        self._configured = True
        
    def load_contracts(self, contracts: dict[int, Contract]) -> None:
        self._contracts = contracts

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("OrderManager: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def set_order_router(self, router: "GlobalOrderRouter") -> None:
        self._order_router = router

    def dispatch(self, target: ModuleType, action: str, data: Any) -> None:
        payload = {
            "action": action,
            "data": data
        }
        self.send(target, payload)

    def receive(self, payload: dict[str, Any], source: ModuleType) -> None:
        action = payload.get("action")
        data = payload.get("data")

        dispatch: dict[tuple[ModuleType, str], Callable] = {
            (ModuleType.PORTFOLIO, "order_request"): self._handle_orders_request,
            (ModuleType.PORTFOLIO, "authorize_order"): self._process_authorization,
            (ModuleType.RISK, "order_request"): self._handle_orders_request,
            (ModuleType.RISK, "authorize_order"): self._process_authorization,
        }

        handler = dispatch.get((source, action))
        if handler:
            handler(data)


    def _create_tracker(self, request: "OrderRequest") -> "OrderTracker":
        contract = self._contracts.get(request.con_id)
        if not contract:
            raise ValueError(f"No contract found for con_id {request.con_id}")

        tracker = OrderTracker.create(request=request, contract=contract)
        return tracker

    def stage_orders(self, requests: list["OrderRequest"]):
        for request in requests:
            tracker = self._create_tracker(request)
            self._pending_orders[request.con_id] = tracker


    def _handle_orders_request(self, orders):
        self.stage_orders(orders)

    def _process_authorization(self, auth_payload: dict[str, Any]) -> None:

        con_id = auth_payload.get("con_id")
        authorized = auth_payload.get("authorized", False)

        if con_id is None or con_id not in self._pending_orders:
            return

        if authorized:
            tracker = self._pending_orders.pop(con_id)
            self.route_order(order=tracker)
            self.dispatch(ModuleType.PORTFOLIO, "order_tracking", tracker)


    def route_order(self, order: "OrderTracker") -> None:
        if self._order_router is None:
            raise RuntimeError("OrderManager: router non configuré (set_order_router() non appelé)")
        if self._key is None:
            raise RuntimeError("OrderManager: key non configurée (configure() non appelé)")

        self._order_router.route_order(session_key=self._key, order=order)








