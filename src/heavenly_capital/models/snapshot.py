from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Optional


@dataclass
class SessionSnapshot:
    date: str
    phase: str
    status: str
    state: str
    error: bool


@dataclass
class MarketSnapshot:
    market_state: str
    trading_state: str
    streaming: bool
    tick_rate: float = 0.0
    last_tick_gap: Optional[float] = None
    subscribed_contracts: int = 0
    clients_connected: int = 0
    orders_tracked: int = 0


@dataclass
class SystemSnapshot:
    status: str
    db_status: str
    runtime_threads: int
    active_sessions: int



@dataclass
class PositionSnapshot:
    con_id: int
    symbol: str
    quantity: Decimal
    avg_price: Optional[Decimal] = None
    market_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    performance: Optional[Decimal] = None


@dataclass
class OrderSnapshot:
    con_id: int
    side: str
    quantity: float
    order_type: str
    status: str
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0


@dataclass
class PortfolioSnapshot:
    portfolio_id: str
    account_id: str
    mode: str
    cash: Optional[Decimal] = None
    stock_value: Optional[Decimal] = None
    total_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    performance: Optional[float] = None
    positions: list[PositionSnapshot] = field(default_factory=list)
    orders: list[OrderSnapshot] = field(default_factory=list)



@dataclass
class KernelSnapshot:
    timestamp: float
    system: SystemSnapshot
    market: MarketSnapshot
    today_session: Optional[SessionSnapshot]
    portfolios: list[PortfolioSnapshot] = field(default_factory=list)


    def as_dict(self):
        return asdict(self)

