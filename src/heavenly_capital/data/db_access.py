from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol, Mapping

from heavenly_capital.models.market_data import AssetType
from heavenly_capital.models.portfolio import Position, PortfolioSnapshot
from heavenly_capital.models.risk import RiskSnapshot
from heavenly_capital.models.tickers import TickerUniverseSnapshot, UniverseSnapshot


class DataAccessLayer(Protocol):
    def get_portfolio_snapshot(self, account_id: str) -> PortfolioSnapshot: ...
    def get_risk_snapshot(self, account_id: str) -> RiskSnapshot: ...
    def get_universe_snapshot(self) -> UniverseSnapshot: ...


class InMemorySessionDAL:
    def __init__(self):
        self._store = None

    def get_portfolio_snapshot(self, account_id: str) -> "PortfolioSnapshot":
        as_of = datetime.now(timezone.utc)

        if account_id == "account_0":
            return PortfolioSnapshot(
                account_id=account_id,
                as_of=as_of,
                base_currency="USD",
                cash=Decimal("100000.00"),
                positions={
                    "AAPL": Position(symbol="AAPL", quantity=Decimal("10"), avg_price=Decimal("175.50")),
                    "MSFT": Position(symbol="MSFT", quantity=Decimal("5"), avg_price=Decimal("410.25")),
                },
                snapshot_version=1,
            )

        if account_id == "account_1":
            return PortfolioSnapshot(
                account_id=account_id,
                as_of=as_of,
                base_currency="USD",
                cash=Decimal("100000.00"),
                positions={},
                snapshot_version=1,
            )

        return PortfolioSnapshot(
            account_id=account_id,
            as_of=as_of,
            base_currency="USD",
            cash=Decimal("0.00"),
            positions={},
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