from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional, Callable
from enum import Enum

from ib_async import Contract, Trade, Fill, CommissionReport, Execution


class OrderStatus(Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(Enum):
    MARKET = "MKT"
    LIMIT = "LMT"

@dataclass(frozen=True)
class OrderRequest:
    # TODO:WARNING add attribut from order
    order_id: str
    account_id: str
    portfolio_id: str

    con_id: int
    side: str  # "BUY" / "SELL"
    quantity: float
    order_type: str  # "MARKET", "LIMIT", etc.
    limit_price: Optional[float] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(
            *,
            account_id: str,
            portfolio_id: str,
            con_id: int,
            side: str,
            quantity: float,
            order_type: str,
            limit_price: Optional[float] = None,
    ) -> "OrderRequest":
        return OrderRequest(
            order_id=uuid4().hex,
            account_id=account_id,
            portfolio_id=portfolio_id,
            con_id=con_id,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
        )


class InvalidOrderTransition(Exception):
    pass


@dataclass
class OrderState:
    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0

    fills_count: int = 0
    commissions_count: int = 0

    on_fully_filled: Optional[Callable[["OrderState"], None]] = None

    on_order_status: Optional[Callable[["Trade", "TrackerEventContext"], None]] = None
    on_fill: Optional[Callable[["Fill", "TrackerEventContext"], None]] = None
    on_commission: Optional[Callable[["Execution", "CommissionReport", "TrackerEventContext"], None]] = None


    def initialize(self, total_quantity: float) -> None:
        if self.status != OrderStatus.CREATED:
            raise InvalidOrderTransition("Order already initialized")

        self.remaining_quantity = total_quantity

    def submit(self) -> None:
        if self.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            return
        if self.status != OrderStatus.CREATED:
            raise InvalidOrderTransition("Only CREATED can move to SUBMITTED")

        self.status = OrderStatus.SUBMITTED

    def _update_position_from_fully_filled(self) -> None:
        if (
                self.status == OrderStatus.FILLED
                and self.commissions_count == self.fills_count
                and self.on_fully_filled is not None
        ):
            self.on_fully_filled(self)
            print(self)


    def apply_fill(self, fill: "Fill", context: "TrackerEventContext") -> None:
        execution = fill.execution
        remaining = max(context.tracker.state.remaining_quantity - execution.shares, 0)

        if self.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            raise InvalidOrderTransition(f"Cannot apply fill in state {self.status}")

        self.filled_quantity += execution.shares
        self.remaining_quantity = remaining
        self.avg_fill_price = execution.avgPrice
        self.fills_count += 1

        self.status = OrderStatus.PARTIALLY_FILLED if remaining > 0 else OrderStatus.FILLED
        if self.status == OrderStatus.FILLED:
            self._update_position_from_fully_filled()

        if self.on_fill:
            self.on_fill(fill, context)


    def apply_commission(self, execution: "Execution", commission: "CommissionReport", context: "TrackerEventContext") -> None:
        self.commission += commission.commission
        self.commissions_count += 1

        if self.on_commission:
            self.on_commission(execution, commission, context)

        self._update_position_from_fully_filled()

    def cancel(self) -> None:
        if self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            raise InvalidOrderTransition(
                f"Cannot cancel from state {self.status}"
            )

        self.status = OrderStatus.CANCELLED

    def reject(self) -> None:
        if self.status != OrderStatus.SUBMITTED:
            raise InvalidOrderTransition(
                f"Cannot reject from state {self.status}"
            )

        self.status = OrderStatus.REJECTED



@dataclass
class OrderTracker:
    request: OrderRequest
    state: OrderState
    contract: Contract
    ib_order_id: Optional[int] = None
    retry_count: int = 0

    @staticmethod
    def create(request: OrderRequest, contract: Optional[Contract] = None) -> "OrderTracker":
        state = OrderState()
        state.initialize(request.quantity)

        if contract is None:
            contract = Contract(conId=request.con_id)

        return OrderTracker(
            request=request,
            state=state,
            contract=contract,
        )

    def apply_status(self, *, trade: "Trade", context: "TrackerEventContext") -> None:

        order = trade.order
        status = trade.orderStatus.status

        if order.permId:
            self.ib_order_id = order.permId

        status_mapping = {
            "Submitted": OrderStatus.SUBMITTED,
            "PreSubmitted": OrderStatus.SUBMITTED,
            "ValidationError": OrderStatus.SUBMITTED,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Inactive": OrderStatus.CANCELLED,
            "ApiCancelled": OrderStatus.CANCELLED,
            "Rejected": OrderStatus.REJECTED,
        }

        mapped_status = status_mapping.get(status)
        if mapped_status == OrderStatus.SUBMITTED:
            self.state.submit()
        elif mapped_status == OrderStatus.CANCELLED:
            self.state.cancel()
        elif mapped_status == OrderStatus.REJECTED:
            self.state.reject()

        if self.state.on_order_status:
            self.state.on_order_status(trade, context)




@dataclass
class TrackerEventContext:
    tracker: OrderTracker
    perm_id: int
    portfolio_id: str
    account_id: str
    con_id: int = field(init=False)

    def __post_init__(self):
        self.con_id = self.tracker.contract.conId
