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

        self._router: Optional["GlobalOrderRouter"] = None

        self._contracts: dict[int, Contract] = {}
        self._pending_orders: Dict[str, OrderTracker] = {}

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

    @property
    def dispatch_table(self) -> dict[ModuleType, dict[str, Callable[[Any], None]]]:
        return {
            ModuleType.PORTFOLIO: {
                "order_request": self._handle_portfolio_orders_request,
                "authorize_order": self._process_portfolio_authorization,
            },
            ModuleType.RISK: {
                "order_request": self._handle_risk_orders_request,
                "authorize_order": self._process_risk_authorization,
            },
        }

    def dispatch(self, target: ModuleType, action: str, data: Any) -> None:
        payload = {
            "action": action,
            "data": data
        }
        self.send(target, payload)

    def set_router(self, router: "GlobalOrderRouter") -> None:
        self._router = router

    def receive(self, payload: Any, source: ModuleType) -> None:
        action = payload.get("action")
        data = payload.get("data")

        if not action:
            raise ValueError("Missing 'action' in payload")

        handler = self.dispatch_table.get(source, {}).get(action)
        if handler:
            handler(data)
        else:
            raise RuntimeError(f"No handler defined for source={source} action={action}")

    def _create_tracker(self, request: "OrderRequest") -> "OrderTracker":
        contract = self._contracts.get(request.con_id)
        if not contract:
            raise ValueError(f"No contract found for con_id {request.con_id}")

        tracker = OrderTracker.create(request=request, contract=contract)
        return tracker

    def stage_orders(self, requests: list["OrderRequest"]):
        for request in requests:
            tracker = self._create_tracker(request)
            self._pending_orders[request.order_id] = tracker

    def _handle_portfolio_orders_request(self, orders):
        self.stage_orders(orders)

    def _handle_risk_orders_request(self, orders):
        # TODO:WARNING TO FINISH
        self.stage_orders(orders)

    def _process_portfolio_authorization(self, auth_payload: dict[str, Any]) -> None:
        order_id = auth_payload.get("order_id")
        authorized = auth_payload.get("authorized", False)

        if order_id is None or order_id not in self._pending_orders:
            return

        if authorized:
            tracker = self._pending_orders.pop(order_id)
            self.route_order(tracker)
            self.send(ModuleType.PORTFOLIO, tracker)

    def _process_risk_authorization(self) : ...


    def route_order(self, order: "OrderTracker") -> None:
        if self._router is None:
            raise RuntimeError("OrderManager: router non configuré (set_router() non appelé)")
        if self._key is None:
            raise RuntimeError("OrderManager: key non configurée (configure() non appelé)")

        self._router.route_order(session_key=self._key, order=order)








