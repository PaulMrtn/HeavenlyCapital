from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol, Mapping

from heavenly_capital.models.market_data import AssetType
from heavenly_capital.models.portfolio import Position, PortfolioSnapshot
from heavenly_capital.models.risk import RiskSnapshot
from heavenly_capital.models.tickers import TickerUniverseSnapshot, UniverseSnapshot


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


    def get_universe_snapshot(self) -> UniverseSnapshot:
        as_of = datetime.now(timezone.utc)

        return UniverseSnapshot(
             as_of=as_of,
             universe_id="SP500",
             constituents=
             {
            "EQ_US_AAPL": TickerUniverseSnapshot(
                internal_code="EQ_US_AAPL",
                symbol="AAPL",
                asset_type=AssetType.STK,
                tickers=["AAPL"],
                updated_at=as_of,
            ),
            "EQ_US_MSFT": TickerUniverseSnapshot(
                internal_code="EQ_US_MSFT",
                symbol="MSFT",
                asset_type=AssetType.STK,
                tickers=["MSFT"],
                updated_at=as_of,
            ),
            "EQ_US_NVDA": TickerUniverseSnapshot(
                internal_code="EQ_US_NVDA",
                symbol="NVDA",
                asset_type=AssetType.STK,
                tickers=["NVDA"],
                updated_at=as_of,
            ),
            }
        )


