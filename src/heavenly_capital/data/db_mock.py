from typing import Sequence
from decimal import Decimal

from sqlalchemy import text, RowMapping
from sqlalchemy import create_engine


def create_postgres_engine(
    user: str,
    password: str,
    host: str = "localhost",
    port: int = 5432,
    dbname: str = "",
    future: bool = True
):

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url, future=future)


engine = create_postgres_engine(
    user="app_rw_local",
    password="B9O59/2kfQm8D8Re2s/eFHCxGnkGtAQdJ3CgA1B1Js2T5uF+npf6Y2cGEnytYU9Y",
    host="localhost",
    port=5432,
    dbname="trading_state_dev"
)


class TradingSessionDB:

    @staticmethod
    def insert_session(session_name: str, account_id: str, mode: str, context: dict | None = None) -> None:
        query = text("""
            INSERT INTO session_registry (session_name, account_id, mode, context)
            VALUES (:session_name, :account_id, :mode, :context)
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "session_name": session_name,
                    "account_id": account_id,
                    "mode": mode,
                    "context": context
                }
            )

    @staticmethod
    def insert_portfolio(
        account_id: str,
        strategy_id: str,
        portfolio_id: str,
        portfolio_name: str,
        cash: float,
        currency: str = "EUR",
        enabled: bool = True
    ) -> None:
        query = text("""
            INSERT INTO portfolio_registry
                (account_id, portfolio_id, portfolio_name, strategy_id, cash, currency, enabled)
            VALUES
                (:account_id, :portfolio_id, :portfolio_name, :strategy_id, :cash, :currency, :enabled)
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "account_id": account_id,
                    "portfolio_id": portfolio_id,
                    "portfolio_name": portfolio_name,
                    "strategy_id": strategy_id,
                    "cash": cash,
                    "currency": currency,
                    "enabled": enabled
                }
            )


    @staticmethod
    def delete_portfolio(account_id: str, portfolio_id: str) -> dict | None:
        query = text("""
            DELETE FROM portfolio_registry
            WHERE account_id = :account_id
              AND portfolio_id = :portfolio_id
            RETURNING id
        """)

        with engine.begin() as conn:
            result = conn.execute(
                query,
                {
                    "account_id": account_id,
                    "portfolio_id": portfolio_id
                }
            )
            deleted = result.mappings().first()

        return deleted

    @staticmethod
    def total_cash_for_session(account_id: str) -> dict[str, Decimal]:
        query = text("""
            SELECT cash, currency
            FROM portfolio_registry
            WHERE account_id = :account_id
        """)

        with engine.connect() as conn:
            result = conn.execute(
                query,
                {"account_id": account_id}
            )
            rows = result.mappings().all()

        totals: dict[str, Decimal] = {}
        for row in rows:
            cash = row["cash"]
            currency = row["currency"]
            totals[currency] = totals.get(currency, Decimal("0.0")) + cash

        return totals


    @staticmethod
    def fetch_all() -> Sequence[RowMapping]:
        query = text("SELECT session_name, account_id, mode, context FROM session_registry")
        with engine.connect() as conn:
            return conn.execute(query).mappings().all()


    @staticmethod
    def fetch_by_account(account_id: str) -> Sequence[RowMapping]:
        query = text("SELECT session_name, account_id, mode, context FROM session_registry WHERE account_id = :account_id")
        with engine.connect() as conn:
            return conn.execute(query, {"account_id": account_id}).mappings().all()


    @staticmethod
    def exists_for_account(account_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM session_registry
            WHERE account_id = :account_id
            LIMIT 1
        """)

        with engine.connect() as conn:
            result = conn.execute(
                query,
                {"account_id": account_id}
            )
            row = result.mappings().first()

        return row is not None

    @staticmethod
    def exists_for_portfolio(portfolio_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM portfolio_registry
            WHERE portfolio_id = :portfolio_id
            LIMIT 1
        """)

        with engine.connect() as conn:
            result = conn.execute(
                query,
                {"portfolio_id": portfolio_id}
            )
            row = result.mappings().first()

        return row is not None

    @staticmethod
    def portfolio_exists_for_account(account_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM portfolio_registry
            WHERE account_id = :account_id
            LIMIT 1
        """)

        with engine.connect() as conn:
            result = conn.execute(
                query,
                {"account_id": account_id}
            )
            row = result.mappings().first()

        return row is not None

    @staticmethod
    def portfolio_exists_for_portfolio_id(portfolio_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM portfolio_registry
            WHERE portfolio_id = :portfolio_id
            LIMIT 1
        """)

        with engine.connect() as conn:
            result = conn.execute(
                query,
                {"portfolio_id": portfolio_id}
            )
            row = result.mappings().first()

        return row is not None

    @staticmethod
    def portfolio_is_enabled(portfolio_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM portfolio_registry
            WHERE portfolio_id = :portfolio_id
              AND enabled = TRUE
            LIMIT 1
        """)

        with engine.connect() as conn:
            result = conn.execute(
                query,
                {"portfolio_id": portfolio_id}
            )
            row = result.mappings().first()

        return row is not None

    @staticmethod
    def fetch_portfolios(account_id: str, only_enabled: bool = True) -> list[dict]:
        query = """
                SELECT portfolio_id, portfolio_name, strategy_id, account_id
                FROM portfolio_registry
                WHERE account_id = :account_id \
                """

        if only_enabled:
            query += " AND enabled = TRUE"

        query = text(query)

        with engine.connect() as conn:
            result = conn.execute(query, {"account_id": account_id})
            portfolios = [dict(row) for row in result.mappings().all()]

        return portfolios