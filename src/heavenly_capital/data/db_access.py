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
            universe_id="SP500_SAMPLE",
            constituents={

                "EQ_US_AAPL": TickerUniverseSnapshot(
                    asset_id="EQ_US_AAPL", symbol="AAPL", asset_type=AssetType.STK, tickers=["AAPL"], updated_at=as_of,
                ),
                "EQ_US_MSFT": TickerUniverseSnapshot(
                    asset_id="EQ_US_MSFT", symbol="MSFT", asset_type=AssetType.STK, tickers=["MSFT"], updated_at=as_of,
                ),
                "EQ_US_NVDA": TickerUniverseSnapshot(
                    asset_id="EQ_US_NVDA", symbol="NVDA", asset_type=AssetType.STK, tickers=["NVDA"], updated_at=as_of,
                ),
                "EQ_US_AMZN": TickerUniverseSnapshot(
                    asset_id="EQ_US_AMZN", symbol="AMZN", asset_type=AssetType.STK, tickers=["AMZN"], updated_at=as_of,
                ),
                "EQ_US_GOOGL": TickerUniverseSnapshot(
                    asset_id="EQ_US_GOOGL", symbol="GOOGL", asset_type=AssetType.STK, tickers=["GOOGL"], updated_at=as_of,
                ),
                "EQ_US_GOOG": TickerUniverseSnapshot(
                    asset_id="EQ_US_GOOG", symbol="GOOG", asset_type=AssetType.STK, tickers=["GOOG"], updated_at=as_of,
                ),
                "EQ_US_AVGO": TickerUniverseSnapshot(
                    asset_id="EQ_US_AVGO", symbol="AVGO", asset_type=AssetType.STK, tickers=["AVGO"], updated_at=as_of,
                ),
                "EQ_US_META": TickerUniverseSnapshot(
                    asset_id="EQ_US_META", symbol="META", asset_type=AssetType.STK, tickers=["META"], updated_at=as_of,
                ),
                "EQ_US_JPM": TickerUniverseSnapshot(
                    asset_id="EQ_US_JPM", symbol="JPM", asset_type=AssetType.STK, tickers=["JPM"], updated_at=as_of,
                ),
                "EQ_US_LLY": TickerUniverseSnapshot(
                    asset_id="EQ_US_LLY", symbol="LLY", asset_type=AssetType.STK, tickers=["LLY"], updated_at=as_of,
                ),
                "EQ_US_V": TickerUniverseSnapshot(
                    asset_id="EQ_US_V", symbol="V", asset_type=AssetType.STK, tickers=["V"], updated_at=as_of,
                ),
                "EQ_US_COST": TickerUniverseSnapshot(
                    asset_id="EQ_US_COST", symbol="COST", asset_type=AssetType.STK, tickers=["COST"], updated_at=as_of,
                ),
                "EQ_US_XOM": TickerUniverseSnapshot(
                    asset_id="EQ_US_XOM", symbol="XOM", asset_type=AssetType.STK, tickers=["XOM"], updated_at=as_of,
                ),
                "EQ_US_WMT": TickerUniverseSnapshot(
                    asset_id="EQ_US_WMT", symbol="WMT", asset_type=AssetType.STK, tickers=["WMT"], updated_at=as_of,
                ),
                "EQ_US_PG": TickerUniverseSnapshot(
                    asset_id="EQ_US_PG", symbol="PG", asset_type=AssetType.STK, tickers=["PG"], updated_at=as_of,
                ),
                "EQ_US_JNJ": TickerUniverseSnapshot(
                    asset_id="EQ_US_JNJ", symbol="JNJ", asset_type=AssetType.STK, tickers=["JNJ"], updated_at=as_of,
                ),
                "EQ_US_HD": TickerUniverseSnapshot(
                    asset_id="EQ_US_HD", symbol="HD", asset_type=AssetType.STK, tickers=["HD"], updated_at=as_of,
                ),
                "EQ_US_ABBV": TickerUniverseSnapshot(
                    asset_id="EQ_US_ABBV", symbol="ABBV", asset_type=AssetType.STK, tickers=["ABBV"], updated_at=as_of,
                ),
                "EQ_US_BAC": TickerUniverseSnapshot(
                    asset_id="EQ_US_BAC", symbol="BAC", asset_type=AssetType.STK, tickers=["BAC"], updated_at=as_of,
                ),
                "EQ_US_KO": TickerUniverseSnapshot(
                    asset_id="EQ_US_KO", symbol="KO", asset_type=AssetType.STK, tickers=["KO"], updated_at=as_of,
                ),
                "EQ_US_NFLX": TickerUniverseSnapshot(
                    asset_id="EQ_US_NFLX", symbol="NFLX", asset_type=AssetType.STK, tickers=["NFLX"], updated_at=as_of),

                "EQ_US_MA": TickerUniverseSnapshot(
                    asset_id="EQ_US_MA", symbol="MA", asset_type=AssetType.STK, tickers=["MA"], updated_at=as_of),

                "EQ_US_UNH": TickerUniverseSnapshot(
                    asset_id="EQ_US_UNH", symbol="UNH", asset_type=AssetType.STK, tickers=["UNH"], updated_at=as_of)

            }
        )