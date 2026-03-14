from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING, Callable
from uuid import UUID

from ib_async import Contract, Execution, CommissionReport, Fill, Trade

from heavenly_capital.core.runtime_config import BaseModule, ModuleType
from heavenly_capital.data.db_mock import TradingSessionDB
from heavenly_capital.models.order import OrderTracker, OrderRequest, TrackerEventContext
from heavenly_capital.strategy.artifacts import ModelSignal

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey, GlobalOrderRouter


tsDB = TradingSessionDB()


class OrderManager(BaseModule):
    def __init__(self) -> None:

        super().__init__()
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._order_router: Optional["GlobalOrderRouter"] = None
        self._contracts: Dict[int, Contract] = {}
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

    @staticmethod
    def _persist_order_status(trade: "Trade", ctx: "TrackerEventContext") -> None:
        tsDB.update_order_in_db(
            trade=trade,
            perm_id=ctx.perm_id,
            portfolio_id=ctx.portfolio_id,
            account_id=ctx.account_id
        )


    @staticmethod
    def _persist_fill(fill: "Fill", ctx: "TrackerEventContext") -> None:
        tsDB.update_fill_in_db(
            execution=fill.execution,
            fill=fill,
            account_id=ctx.account_id,
            portfolio_id=ctx.portfolio_id,
            con_id=ctx.con_id
        )

    @staticmethod
    def _persist_commission(execution: "Execution", commission: "CommissionReport", ctx: "TrackerEventContext") -> None:
        tsDB.update_commission_in_db(
            execution=execution,
            commission=commission,
            account_id=ctx.account_id,
            portfolio_id=ctx.portfolio_id,
            con_id=ctx.con_id
        )


    def _create_tracker(self, request: "OrderRequest") -> "OrderTracker":
        contract = self._contracts.get(request.con_id)
        if not contract:
            raise ValueError(f"No contract found for con_id {request.con_id}")

        tracker = OrderTracker.create(request=request, contract=contract)

        tracker.state.on_order_status = self._persist_order_status
        tracker.state.on_fill = self._persist_fill
        tracker.state.on_commission = self._persist_commission

        return tracker



    def stage_orders(self, requests: list["OrderRequest"]):
        for request in requests:
            tracker = self._create_tracker(request)
            self._pending_orders[request.con_id] = tracker


    def _handle_orders_request(self, orders):
        self.stage_orders(orders)

    def _process_authorization(self, event: "ModelSignal") -> None:
        con_id = event.conid
        authorized = event.output.decision

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

        self._order_router.route_order(
            session_key=self._key,
            order=order
        )









