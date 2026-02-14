from decimal import Decimal
from typing import Optional, Dict, List, Any

from heavenly_capital.models.portfolio import PortfolioLedger
from heavenly_capital.data.db_mock import TradingSessionDB


class SessionService:

    def __init__(self, db: TradingSessionDB):
        self._db = db
        self._portfolios: Dict[str, List["PortfolioLedger"]] = {}

    def create_session(
            self,
            session_name: str,
            account_id: str,
            mode: str,
            context: Dict[str, Any] = None,
    ) -> None:

        if self._db.exists_for_account(account_id):
            raise ValueError(
                f"A session already exists for account_id={account_id}"
            )

        self._db.insert_session(session_name, account_id, mode, context)

    def create_portfolio(
            self,
            account_id: str,
            strategy_id: str,
            portfolio_id: str,
            portfolio_name: str,
            cash_amount: Optional[Decimal | float] = None,
            currency: str = "EUR",
            enabled: bool = True,
    ) -> None:

        sessions = self._db.fetch_by_account(account_id)
        if not sessions:
            raise ValueError(f"No session found for account_id={account_id}")

        session_mode = sessions[0].mode.upper()

        if session_mode == "LIVE":
            if cash_amount is not None:
                raise ValueError(
                    "cash_amount cannot be specified when creating a LIVE session"
                )

            if self._db.portfolio_exists_for_account(account_id):
                raise ValueError(
                    f"Un portefeuille existe déjà pour le compte LIVE {account_id}"
                )

            if self._db.portfolio_exists_for_portfolio_id(portfolio_id):
                raise ValueError(
                    f"Portfolio id '{portfolio_id}' already exists in the database"
                )

            self._db.insert_portfolio(account_id, strategy_id, portfolio_id, portfolio_name, 0.0, currency, enabled)

        else:
            if cash_amount is None:
                raise ValueError(
                    "cash_amount must be specified when creating a PAPER session"
                )

            if self._db.portfolio_exists_for_portfolio_id(portfolio_id):
                raise ValueError(
                    f"Portfolio with id '{portfolio_id}' already exists in the database"
                )

            self._db.insert_portfolio(account_id, strategy_id, portfolio_id, portfolio_name, cash_amount, currency, enabled)


    def delete_portfolio(
            self,
            account_id: str,
            portfolio_id: str,
    ) -> None:

        if not self._db.portfolio_exists_for_portfolio_id(portfolio_id):
            raise ValueError(
                f"No portfolio with id '{portfolio_id}' exists in the database"
            )

        deleted = self._db.delete_portfolio(account_id, portfolio_id)
        if not deleted:
            raise ValueError(
                f"No portfolio named '{portfolio_id}' found for account_id={account_id}"
            )

    def is_portfolio_enabled(self, portfolio_id: str) -> bool:
        if not self._db.portfolio_exists_for_portfolio_id(portfolio_id):
            raise ValueError(
                f"No portfolio with id '{portfolio_id}' exists in the database"
            )

        return self._db.portfolio_is_enabled(portfolio_id)