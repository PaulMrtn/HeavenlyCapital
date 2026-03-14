from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict


@dataclass(frozen=True)
class RiskSnapshot:
    account_id: str
    stop_loss_pct_by_symbol: Dict[str, Decimal]          # ex: {"AAPL": Decimal("0.05")}
    stop_loss_price_by_symbol: Dict[str, Decimal]        # ex: {"AAPL": Decimal("175.50")}


@dataclass(slots=True)
class RiskState:
    account_id: str
    stop_loss_pct_by_symbol: Dict[str, Decimal] = field(default_factory=dict)
    stop_loss_price_by_symbol: Dict[str, Decimal] = field(default_factory=dict)

    @classmethod
    def from_snapshot(cls, snapshot: "RiskSnapshot") -> "RiskState":
        return cls(
            account_id=snapshot.account_id,
            stop_loss_pct_by_symbol=dict(snapshot.stop_loss_pct_by_symbol),
            stop_loss_price_by_symbol=dict(snapshot.stop_loss_price_by_symbol),
        )

    def to_snapshot(self) -> "RiskSnapshot":
        return RiskSnapshot(
            account_id=self.account_id,
            stop_loss_pct_by_symbol=dict(self.stop_loss_pct_by_symbol),
            stop_loss_price_by_symbol=dict(self.stop_loss_price_by_symbol),
        )
