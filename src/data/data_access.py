from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Protocol, Optional, TYPE_CHECKING, Mapping
from uuid import UUID

from src.models.portfolio import Position, PortfolioSnapshot
from src.models.risk import RiskSnapshot


class DataAccessLayer(Protocol):
    pass


class InMemorySessionDAL:
    def __init__(self):
        self._store = None

    def get_portfolio_snapshot(self, account_id: str) -> "PortfolioSnapshot":
        as_of = datetime.now(timezone.utc)

        base_currency = "USD"
        cash = Decimal("100000.00")

        positions: Mapping[str, "Position"] = {
            "AAPL": Position(symbol="AAPL", quantity=Decimal("10"), avg_price=Decimal("175.50")),
            "MSFT": Position(symbol="MSFT", quantity=Decimal("5"), avg_price=Decimal("410.25")),
        }

        return PortfolioSnapshot(
            account_id=account_id,
            as_of=as_of,
            base_currency=base_currency,
            cash=cash,
            positions=positions,
            snapshot_version=1,
        )


    def get_risk_snapshot(self, account_id: str) -> "RiskSnapshot":
        as_of = datetime.now(timezone.utc)

        return RiskSnapshot(
            account_id=account_id,
            as_of=as_of,
            stop_loss_pct_by_symbol={"AAPL": Decimal("0.05")},
            stop_loss_price_by_symbol={"AAPL": Decimal("175.50")},
        )
