from dataclasses import dataclass
from datetime import datetime, UTC
from decimal import Decimal
from typing import Dict, Mapping, Optional, Any


@dataclass
class Position:
    symbol: str
    quantity: Decimal
    avg_price: Decimal

    market_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    updated_at: Optional[datetime] = None

    def mark_to_market(self, market_data: Dict[str, Any]) -> None:
        #TODO:WARNING: turn bid to last
        last = market_data.get("bid")
        timestamp = market_data.get("timestamp")

        if last is None:
            return

        #TODO:WARNING convert value to Decimal a the root (Client)
        last_price = Decimal(last) if isinstance(last, str) else Decimal(str(last))

        self.market_price = last_price
        self.market_value = self.quantity * last_price
        self.unrealized_pnl = (last_price - self.avg_price) * self.quantity

        if timestamp is not None:
            self.updated_at = datetime.fromtimestamp(timestamp, UTC)

    @property
    def performance(self) -> Optional[Decimal]:
        if self.market_price is not None and self.avg_price != 0:
            return (self.market_price - self.avg_price) / self.avg_price
        return None


    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_price": self.avg_price,
            "market_price": self.market_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class PortfolioBalance:
    cash: Decimal
    stock_market_value: Decimal
    unrealized_pnl: Decimal
    total_commission: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    portfolio_id : str
    account_id: str
    base_currency: str
    balance: PortfolioBalance
    positions: Mapping[int, Position]


@dataclass
class PortfolioTarget:
    weights: Dict[int, float]
    rebalance_date: str  # datetime.date


@dataclass
class Portfolio:
    account_id: str
    portfolio_id: str
    base_currency: str
    balance: PortfolioBalance
    positions: Dict[int, Position]

    updated_at: Optional[datetime] = None

    @classmethod
    def from_snapshot(cls, snapshot: PortfolioSnapshot) -> "Portfolio":
        return cls(
            account_id=snapshot.account_id,
            portfolio_id=snapshot.portfolio_id,
            base_currency=snapshot.base_currency,
            balance=snapshot.balance,
            positions=dict(snapshot.positions)
        )

    def to_snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            account_id=self.account_id,
            portfolio_id=self.portfolio_id,
            base_currency=self.base_currency,
            balance=self.balance,
            positions=dict(self.positions)
        )

    def iter_db_positions(self):
        for con_id, pos in self.positions.items():
            if pos.market_price is None:
                continue
            yield con_id, pos

    @property
    def total_value(self) -> Decimal:
        positions_value = sum(
            p.market_value for p in self.positions.values() if p.market_value is not None
        )
        return self.balance.cash + positions_value

    def refresh_balance(self) -> None:
        stock_value = sum(
            (p.market_value for p in self.positions.values() if p.market_value is not None),
            start=Decimal("0")
        )

        unrealized = sum(
            (p.unrealized_pnl for p in self.positions.values() if p.unrealized_pnl is not None),
            start=Decimal("0")
        )

        self.balance.stock_market_value = stock_value
        self.balance.unrealized_pnl = unrealized

        self.updated_at = max(
            (p.updated_at for p in self.positions.values() if p.updated_at is not None),
            default=None
        )

    @property
    def weights(self) -> dict[str, float]:
        total = self.total_value
        if total == 0:
            return {}

        weights_dict = {}
        for symbol, pos in self.positions.items():
            if pos.market_value is not None:
                weights_dict[symbol] = float(pos.market_value / total)
            else:
                weights_dict[symbol] = 0.0

        weights_dict["CASH"] = float(self.balance.cash / total)
        return weights_dict

    @property
    def performance(self) -> Optional[float]:
        if not self.positions or not self.weights:
            return None

        perf = 0.0
        for symbol, weight in self.weights.items():
            if symbol == "CASH":
                continue

            pos = self.positions.get(int(symbol))
            if pos and pos.performance is not None:
                perf += float(pos.performance) * weight

        return perf

    @property
    def performance_by_pnl(self) -> Optional[float]:
        if not self.positions:
            return None

        total_cost = sum(p.avg_price * p.quantity for p in self.positions.values())
        total_market = sum(p.market_value for p in self.positions.values() if p.market_value is not None)

        if total_market is None or (total_cost + self.balance.cash) == 0:
            return None

        total_portfolio_value = total_market + self.balance.cash
        return float((total_portfolio_value - (total_cost + self.balance.cash)) / (total_cost + self.balance.cash))


#TODO:WARNING Why there is a spread between performance and performance_by_pnl?