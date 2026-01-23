from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict


@dataclass(frozen=True)
class RiskSnapshot:
    account_id: str
    as_of: datetime
    stop_loss_pct_by_symbol: Dict[str, Decimal]          # ex: {"AAPL": Decimal("0.05")}
    stop_loss_price_by_symbol: Dict[str, Decimal]        # ex: {"AAPL": Decimal("175.50")}
    snapshot_version: int = 1


@dataclass(slots=True)
class RiskState:
    account_id: str
    as_of: datetime
    stop_loss_pct_by_symbol: Dict[str, Decimal] = field(default_factory=dict)
    stop_loss_price_by_symbol: Dict[str, Decimal] = field(default_factory=dict)
    snapshot_version: int = 1

    @classmethod
    def from_snapshot(cls, snapshot: "RiskSnapshot") -> "RiskState":
        return cls(
            account_id=snapshot.account_id,
            as_of=snapshot.as_of,
            stop_loss_pct_by_symbol=dict(snapshot.stop_loss_pct_by_symbol),
            stop_loss_price_by_symbol=dict(snapshot.stop_loss_price_by_symbol),
            snapshot_version=snapshot.snapshot_version,
        )

    def to_snapshot(self) -> "RiskSnapshot":
        return RiskSnapshot(
            account_id=self.account_id,
            as_of=self.as_of,
            stop_loss_pct_by_symbol=dict(self.stop_loss_pct_by_symbol),
            stop_loss_price_by_symbol=dict(self.stop_loss_price_by_symbol),
            snapshot_version=self.snapshot_version,
        )
