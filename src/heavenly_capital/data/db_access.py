from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from heavenly_capital.models.portfolio import PortfolioSnapshot
from heavenly_capital.models.risk import RiskSnapshot
from heavenly_capital.models.tickers import UniverseSnapshot


class DataAccessLayer(Protocol):
    def get_portfolio_snapshot(self, account_id: str) -> PortfolioSnapshot: ...
    def get_risk_snapshot(self, account_id: str) -> RiskSnapshot: ...
    def get_universe_snapshot(self) -> UniverseSnapshot: ...


class InMemorySessionDAL:
    def __init__(self):
        self._store = None

    def get_risk_snapshot(self, account_id: str) -> "RiskSnapshot":
        return RiskSnapshot(
            account_id=account_id,
            stop_loss_pct_by_symbol={"AAPL": Decimal("0.05")},
            stop_loss_price_by_symbol={"AAPL": Decimal("175.50")},
        )