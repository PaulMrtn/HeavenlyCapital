from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional
from enum import Enum

from ib_async import Contract


class OrderStatus(Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    session_id: str
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
            session_id: str,
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
            session_id=session_id,
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

    def initialize(self, total_quantity: float) -> None:
        if self.status != OrderStatus.CREATED:
            raise InvalidOrderTransition("Order already initialized")

        self.remaining_quantity = total_quantity

    def submit(self) -> None:
        if self.status != OrderStatus.CREATED:
            raise InvalidOrderTransition("Only CREATED can move to SUBMITTED")

        self.status = OrderStatus.SUBMITTED

    def apply_fill(
            self,
            *,
            filled: float,
            remaining: float,
            avg_price: float,
    ) -> None:

        if self.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            raise InvalidOrderTransition(
                f"Cannot apply fill in state {self.status}"
            )

        self.filled_quantity += filled
        self.remaining_quantity -= filled
        self.avg_fill_price = avg_price

        if remaining > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
        else:
            self.status = OrderStatus.FILLED

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

    def apply_status(
        self,
        *,
        ib_order_id: Optional[int] = None,
        status: str,
        filled: float = 0.0,
        remaining: float = 0.0,
        avg_fill_price: float = 0.0,
    ) -> None:

        if ib_order_id is not None:
            self.ib_order_id = ib_order_id

        status_mapping = {
            "Submitted": OrderStatus.SUBMITTED,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Inactive": OrderStatus.CANCELLED,
            "ApiCancelled": OrderStatus.CANCELLED,
            "Rejected": OrderStatus.REJECTED,
        }
        mapped_status = status_mapping.get(status, None)

        if mapped_status == OrderStatus.SUBMITTED:
            self.state.submit()
        elif mapped_status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
            self.state.apply_fill(filled=filled, remaining=remaining, avg_price=avg_fill_price)
        elif mapped_status == OrderStatus.CANCELLED:
            self.state.cancel()
        elif mapped_status == OrderStatus.REJECTED:
            self.state.reject()