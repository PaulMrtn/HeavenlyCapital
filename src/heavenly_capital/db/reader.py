from __future__ import annotations

import json
from typing import Sequence, Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import RowMapping, text

from heavenly_capital.db.connector import DBConnector


class DataAccessLayer:
    def __init__(self, connector: DBConnector):
        self._connector = connector


    def get_session_by_date(self, session_date: "date") -> Optional[RowMapping]:
    # TODO:WARNING : Ensure that all dates are synchronized between the application, the broker, and the NYSE time zone

        query = text("""
            SELECT session_id, session_date, status, phase, state, error
            FROM trading.market_day_session
            WHERE session_date = :session_date
            LIMIT 1
        """)

        with self._connector.get_connection() as conn:
            return conn.execute(query, {"session_date": session_date}).mappings().first()


    def fetch_all_sessions(self) -> Sequence[RowMapping]:
        query = text("""
                     SELECT account_name, account_id, mode, context
                     FROM trading.account_registry
                     """)

        with self._connector.get_connection() as conn:
            return conn.execute(query).mappings().all()


    def fetch_sessions_by_account(self, account_id: str) -> Sequence[RowMapping]:
        query = text("""
            SELECT account_name, account_id, mode, context
            FROM trading.account_registry
            WHERE account_id = :account_id
        """)

        with self._connector.get_connection() as conn:
            return conn.execute(query, {"account_id": account_id}).mappings().all()


    def session_exists_for_account(self, account_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM trading.account_registry
            WHERE account_id = :account_id
            LIMIT 1
        """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"account_id": account_id})
            return result.mappings().first() is not None


    def exists_for_portfolio(self, portfolio_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM trading.portfolio_registry
            WHERE portfolio_id = :portfolio_id
            LIMIT 1
        """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"portfolio_id": portfolio_id})
            row = result.mappings().first()

        return row is not None

    def portfolio_exists_for_account(self, account_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM trading.portfolio_registry
            WHERE account_id = :account_id
            LIMIT 1
        """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"account_id": account_id})
            return result.mappings().first() is not None


    def portfolio_is_enabled(self, portfolio_id: str) -> bool:
        query = text("""
            SELECT 1
            FROM trading.portfolio_registry
            WHERE portfolio_id = :portfolio_id
              AND enabled = TRUE
            LIMIT 1
        """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"portfolio_id": portfolio_id})
            return result.mappings().first() is not None


    def fetch_trading_sessions(self) -> list[dict]:
        sessions_query = """
                         SELECT account_name, account_id, mode, context
                         FROM trading.account_registry \
                         """

        portfolios_query = """
                           SELECT portfolio_id, portfolio_name, strategy_id, account_id
                           FROM trading.portfolio_registry
                           WHERE account_id = :account_id \
                             AND enabled = TRUE \
                           """

        sessions: list[dict] = []
        with self._connector.get_connection() as conn:
            all_sessions = conn.execute(text(sessions_query)).mappings().all()
            for session_row in all_sessions:
                account_id = session_row["account_id"]
                portfolios_rows = conn.execute(
                    text(portfolios_query),
                    {"account_id": account_id}
                ).mappings().all()

                session_dict = dict(session_row)
                session_dict["portfolios"] = [dict(p) for p in portfolios_rows]
                sessions.append(session_dict)

        return sessions

    def fetch_contracts(self) -> list[dict]:
        query = text("""
                     SELECT con_id, symbol, sec_type, exchange, primary_exchange, currency
                     FROM trading.contracts
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query)
            return [dict(row) for row in result.mappings().all()]


    def fetch_positions(self, portfolio_id: str) -> list[dict]:
        query = text("""
                     SELECT p.account_id,
                            p.portfolio_id,
                            p.con_id,
                            c.symbol,
                            p.quantity,
                            p.avg_cost,
                            p.market_price,
                            p.market_value,
                            p.unrealized_pnl,
                            p.updated_at
                     FROM trading.positions p
                              JOIN trading.contracts c
                                   ON p.con_id = c.con_id
                     WHERE p.portfolio_id = :portfolio_id
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"portfolio_id": portfolio_id})
            return [dict(row) for row in result.mappings().all()]


    def fetch_instruments(self) -> list[dict]:
        query = text("""
            SELECT 
                c.con_id,
                c.symbol,
                c.sec_type,
                c.exchange,
                c.primary_exchange,
                c.currency,
                i.long_name,
                i.sector
            FROM trading.contracts c
            LEFT JOIN trading.instruments i
                ON c.instrument_id = i.instrument_id
        """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query)
            return [dict(row) for row in result.mappings().all()]


    def fetch_portfolio_targets(self, portfolio_id: str, rebalance_date: str) -> list[dict]:
        query = text("""
                     SELECT t.target_id,
                            t.rebalance_date,
                            t.tolerance,
                            w.con_id,
                            w.target_weight
                     FROM trading.portfolio_targets t
                              JOIN trading.portfolio_target_weights w ON t.target_id = w.target_id
                     WHERE t.portfolio_id = :portfolio_id
                       AND t.rebalance_date = :rebalance_date
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"portfolio_id": portfolio_id, "rebalance_date": rebalance_date})
            return [dict(row) for row in result.mappings().all()]


    def fetch_portfolio_thresholds(self, portfolio_id: str | None = None) -> list[dict]:
        if portfolio_id:
            query = text("""
                         SELECT portfolio_id, con_id, threshold_pct
                         FROM trading.portfolio_thresholds
                         WHERE portfolio_id = :portfolio_id
                         """)
            params = {"portfolio_id": portfolio_id}
        else:
            query = text("""
                         SELECT portfolio_id, con_id, threshold_pct
                         FROM trading.portfolio_thresholds
                         """)
            params = {}

        with self._connector.get_connection() as conn:
            result = conn.execute(query, params)
            return [dict(row) for row in result.mappings().all()]


    def check_rebalance_date(self, portfolio_id: str, today: datetime) -> bool:
        query = text("""
                     SELECT 1
                     FROM trading.portfolio_targets
                     WHERE portfolio_id = :portfolio_id
                       AND rebalance_date = :today
                     LIMIT 1
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"portfolio_id": portfolio_id, "today": today}).fetchone()
            return result is not None


    def get_sent_order_refs_today(self, portfolio_id: str, today: date) -> set[str]:
        query = text("""
                     SELECT DISTINCT order_ref
                     FROM trading.orders
                     WHERE portfolio_id = :portfolio_id
                       AND DATE(created_at AT TIME ZONE 'America/New_York') = :today
                       AND status IN ('Submitted', 'PreSubmitted', 'PartiallyFilled', 'Filled')
                       AND order_ref IS NOT NULL
                     """)
        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"portfolio_id": portfolio_id, "today": today})
            return {row["order_ref"] for row in result.mappings().all()}


    def get_account_total_cash(self, account_id: str, currency: str = "USD") -> Optional[Decimal]:
        query = text("""
                     SELECT total_cash_balance
                     FROM trading.account_balances
                     WHERE account_id = :account_id
                       AND currency = :currency
                     LIMIT 1
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"account_id": account_id, "currency": currency}).scalar_one_or_none()

        return Decimal(result) if result is not None else None

    def get_portfolio_balance(self, portfolio_id: str, account_id: str, currency: str = "USD") -> dict:
        query = text("""
                     SELECT total_cash_balance, stock_market_value, unrealized_pnl
                     FROM trading.portfolio_balances
                     WHERE portfolio_id = :portfolio_id
                       AND account_id = :account_id
                       AND currency = :currency
                     LIMIT 1
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {
                "portfolio_id": portfolio_id,
                "account_id": account_id,
                "currency": currency
            }).first()

        if result is None:
            return {
                "total_cash_balance": Decimal("0"),
                "stock_market_value": Decimal("0"),
                "unrealized_pnl": Decimal("0")
            }

        total_cash_balance, stock_market_value, unrealized_pnl = result
        return {
            "total_cash_balance": Decimal(total_cash_balance),
            "stock_market_value": Decimal(stock_market_value),
            "unrealized_pnl": Decimal(unrealized_pnl)
        }


    def model_is_enabled(self, model_name: str, version: float) -> bool:
        query = text("""
            SELECT 1
            FROM trading.models_registry
            WHERE model_name = :model_name
              AND version = :version
              AND enabled = TRUE
            LIMIT 1
        """)

        with self._connector.get_connection() as conn:
            result = conn.execute(
                query,
                {"model_name": model_name, "version": version}
            )
            return result.mappings().first() is not None


    def get_forecast_models_configs(self) -> List[Dict[str, Any]]:
        query = text("""
            SELECT mr.model_name,
                   mr.version,
                   mr.model_type,
                   mr.path,
                   mr.description,
                   pm.portfolio_id
            FROM trading.models_registry mr
                     LEFT JOIN trading.portfolio_models pm
                       ON mr.model_name = pm.model_name
                          AND mr.version = pm.version
            WHERE mr.enabled = TRUE
            ORDER BY pm.portfolio_id NULLS LAST, mr.model_type, mr.model_name
        """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query)
            rows = result.mappings().all()

        return [dict(row) for row in rows]


    def fetch_positions_and_targets(self, today: str) -> List[Dict]:
        query = text("""
                     WITH portfolio_totals AS (SELECT account_id,
                                                      portfolio_id,
                                                      SUM(market_value) AS total_value
                                               FROM trading.positions
                                               GROUP BY account_id, portfolio_id),
                          positions_with_weight AS (SELECT p.account_id,
                                                           sr.mode AS session_mode,
                                                           p.portfolio_id,
                                                           p.con_id,
                                                           c.symbol,
                                                           p.market_value,
                                                           pt.total_value,
                                                           CASE
                                                               WHEN pt.total_value > 0
                                                                   THEN p.market_value / pt.total_value
                                                               ELSE 0
                                                               END AS pos_w
                                                    FROM trading.positions p
                                                             JOIN trading.contracts c ON p.con_id = c.con_id
                                                             JOIN trading.account_registry sr ON p.account_id = sr.account_id
                                                             JOIN portfolio_totals pt
                                                                  ON p.account_id = pt.account_id
                                                                      AND p.portfolio_id = pt.portfolio_id),
                          targets_only AS (SELECT t.account_id,
                                                  sr.mode         AS session_mode,
                                                  t.portfolio_id,
                                                  w.con_id,
                                                  c.symbol,
                                                  w.target_weight AS target_w
                                           FROM trading.portfolio_targets t
                                                    JOIN trading.portfolio_target_weights w ON t.target_id = w.target_id
                                                    JOIN trading.contracts c ON w.con_id = c.con_id
                                                    JOIN trading.account_registry sr ON t.account_id = sr.account_id
                                           WHERE t.rebalance_date = :today),
                          combined AS (

                              SELECT pw.account_id,
                                     pw.session_mode,
                                     pw.portfolio_id,
                                     pw.con_id,
                                     pw.symbol,
                                     pw.pos_w,
                                     tw.target_weight AS target_w
                              FROM positions_with_weight pw
                                       LEFT JOIN trading.portfolio_targets t
                                                 ON pw.account_id = t.account_id
                                                     AND pw.portfolio_id = t.portfolio_id
                                                     AND t.rebalance_date = :today
                                       LEFT JOIN trading.portfolio_target_weights tw
                                                 ON t.target_id = tw.target_id
                                                     AND pw.con_id = tw.con_id

                              UNION ALL

                              SELECT t.account_id,
                                     t.session_mode,
                                     t.portfolio_id,
                                     t.con_id,
                                     t.symbol,
                                     NULL::NUMERIC AS pos_w,
                                     t.target_w
                              FROM targets_only t
                                       LEFT JOIN positions_with_weight pw
                                                 ON pw.account_id = t.account_id
                                                     AND pw.portfolio_id = t.portfolio_id
                                                     AND pw.con_id = t.con_id
                              WHERE pw.con_id IS NULL)

                     SELECT account_id,
                            session_mode,
                            portfolio_id,
                            con_id,
                            symbol,
                            pos_w,
                            target_w,
                            CASE
                                WHEN target_w IS NOT NULL AND pos_w IS NULL THEN 'BUY'
                                WHEN target_w IS NULL AND pos_w IS NOT NULL
                                    AND NOT EXISTS (SELECT 1
                                                    FROM trading.portfolio_targets t2
                                                    WHERE t2.account_id = combined.account_id
                                                      AND t2.portfolio_id = combined.portfolio_id
                                                      AND t2.rebalance_date = :today) THEN 'HOLD'
                                WHEN target_w IS NULL AND pos_w IS NOT NULL THEN 'SELL'
                                WHEN pos_w < target_w THEN 'BUY'
                                WHEN pos_w > target_w THEN 'SELL'
                                ELSE 'HOLD'
                                END AS action
                     FROM combined
                     ORDER BY portfolio_id, con_id
                     """)

        with self._connector.get_connection() as conn:
            rows = conn.execute(query, {"today": today}).mappings().all()
            return [dict(row) for row in rows]


    def feature_exists(self, uid: str) -> bool:
        query = text("""
                     SELECT 1
                     FROM trading.feature_registry
                     WHERE uid = :uid
                     LIMIT 1
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query, {"uid": uid})
            return result.mappings().first() is not None


    def get_features_config(self) -> List[Dict[str, Any]]:
        query = text("""
                     SELECT category,
                            plugin,
                            scope,
                            kind,
                            fields,
                            freqs,
                            params,
                            priority,
                            cache,
                            is_active
                     FROM trading.feature_registry
                     WHERE is_active = TRUE
                     ORDER BY priority
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query)
            rows = result.mappings().all()

        specs = []
        for row in rows:
            row_dict = dict(row)

            if isinstance(row_dict.get("freqs"), str):
                row_dict["freqs"] = json.loads(row_dict["freqs"])

            if isinstance(row_dict.get("params"), str):
                row_dict["params"] = json.loads(row_dict["params"])

            specs.append(row_dict)

        return specs


    #TODO: LOW temporary/ debug fn
    def fetch_first_rate_symbols(self) -> set[str]:
        query = text("""
                     SELECT first_rate_symbol
                     FROM trading.first_rate_reference
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query)
            return {row["first_rate_symbol"] for row in result.mappings().all()}

    def fetch_first_rate_symbol_to_norgate(self) -> dict[str, int]:
        query = text("""
                     SELECT first_rate_symbol, norgate_id
                     FROM trading.first_rate_reference
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(query)
            return {row["first_rate_symbol"]: row["norgate_id"] for row in result.mappings().all()}

    def fetch_universe_prices(
            self,
            universe_code: str,
            start_date: str
    ) -> List[Dict[str, Any]]:

        query = text("""
                     SELECT i.symbol,
                            p.date,
                            p.close
                     FROM market.prices_daily p
                              JOIN trading.instruments i
                                   ON p.instrument_id = i.instrument_id
                              JOIN trading.universe_membership um
                                   ON i.norgate_id = um.norgate_id
                              JOIN trading.universes u
                                   ON um.universe_id = u.universe_id
                     WHERE u.code = :universe_code
                       AND p.adjustment_type = 'TOTAL_RETURN'
                       AND p.date >= :start_date
                       AND p.date >= um.valid_from
                       AND (um.valid_to IS NULL OR p.date <= um.valid_to)
                     ORDER BY i.symbol, p.date
                     """)

        with self._connector.get_connection() as conn:
            result = conn.execute(
                query,
                {
                    "universe_code": universe_code,
                    "start_date": start_date
                }
            )

            return result.mappings().all()

    def get_last_price_date(self) -> date | None:
        query = text("""
                     SELECT MAX(date)
                     FROM market.prices_daily
                     """)

        with self._connector.get_connection() as conn:
            return conn.execute(query).scalar()


    def get_norgate_ids(self) -> list[int]:
        query = text("""
                     SELECT norgate_id
                     FROM trading.instruments
                     WHERE norgate_id IS NOT NULL
                     """)
        with self._connector.get_connection() as conn:
            result = conn.execute(query)
            return [row["norgate_id"] for row in result.mappings().all()]


