from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, Mapping, Optional, Union


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    quantity: Decimal
    avg_price: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    account_id: str
    as_of: datetime
    base_currency: str
    cash: Decimal
    positions: Mapping[str, Position]
    snapshot_version: int = 1

@dataclass(slots=True)
class Portfolio:
    account_id: str
    as_of: datetime
    base_currency: str
    cash: Decimal
    positions: Dict[str, Position]
    snapshot_version: int = 1

    @classmethod
    def from_snapshot(cls, snapshot: PortfolioSnapshot) -> "Portfolio":
        return cls(
            account_id=snapshot.account_id,
            as_of=snapshot.as_of,
            base_currency=snapshot.base_currency,
            cash=snapshot.cash,
            positions=dict(snapshot.positions),
            snapshot_version=snapshot.snapshot_version,
        )

    def to_snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            account_id=self.account_id,
            as_of=self.as_of,
            base_currency=self.base_currency,
            cash=self.cash,
            positions=dict(self.positions),
            snapshot_version=self.snapshot_version,
        )


@dataclass(frozen=True, slots=True)
class PortfolioLedger:
    account_id: str
    strategy_id: str
    portfolio_id: str
    portfolio_name: str
    enabled: bool
    cash: Dict[str, Optional[Union[Decimal, float]]] = field(default_factory=dict)
