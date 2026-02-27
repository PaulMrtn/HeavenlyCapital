from dataclasses import dataclass, field
from datetime import datetime, UTC
from decimal import Decimal
from typing import Dict, Mapping, Optional, Union, Any


@dataclass(frozen=True, slots=True)
class PortfolioLedger:
    account_id: str
    strategy_id: str
    portfolio_id: str
    portfolio_name: str
    enabled: bool
    cash: Dict[str, Optional[Union[Decimal, float]]] = field(default_factory=dict)


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

        last_price = Decimal(str(last))

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


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    account_id: str
    as_of: datetime
    base_currency: str
    cash: Decimal
    positions: Mapping[int, Position]


@dataclass
class PortfolioTarget:
    weights: Dict[int, float]
    rebalance_date: str  # datetime.date

@dataclass(slots=True)
class Portfolio:
    account_id: str
    as_of: Optional[datetime]
    base_currency: str
    cash: Decimal
    positions: Dict[int, Position]

    @classmethod
    def from_snapshot(cls, snapshot: PortfolioSnapshot) -> "Portfolio":
        return cls(
            account_id=snapshot.account_id,
            as_of=snapshot.as_of,
            base_currency=snapshot.base_currency,
            cash=snapshot.cash,
            positions=dict(snapshot.positions)
        )

    def to_snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            account_id=self.account_id,
            as_of=self.as_of,
            base_currency=self.base_currency,
            cash=self.cash,
            positions=dict(self.positions)
        )

    @property
    def total_value(self) -> Decimal:
        positions_value = sum(
            p.market_value for p in self.positions.values() if p.market_value is not None
        )
        return self.cash + positions_value

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

        weights_dict["CASH"] = float(self.cash / total)
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

        if total_market is None or (total_cost + self.cash) == 0:
            return None

        total_portfolio_value = total_market + self.cash
        return float((total_portfolio_value - (total_cost + self.cash)) / (total_cost + self.cash))




    # def add_position(self, position: Position):
    #     self.positions[position.symbol] = position
    #
    # def remove_position(self, symbol: str):
    #     if symbol in self.positions:
    #         del self.positions[symbol]

