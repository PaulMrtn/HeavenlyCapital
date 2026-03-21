from __future__ import annotations

from typing import Sequence

from sqlalchemy import text, RowMapping
from sqlalchemy import create_engine


# TODO:LOW – these objects should remain in the business layer and not be used directly in functions


class UnitOfWork:
    def __enter__(self):
        self.conn = engine.connect()        # Connexion normale
        self.trans = self.conn.begin()      # Transaction explicite
        return self.conn                    # On retourne la connexion pour l'utiliser

    def __exit__(self, exc_type, exc, tb):
        try :
            if exc_type:
                self.trans.rollback()
            else:
                self.trans.commit()
        finally:
            self.conn.close()

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
    def fetch_all_sessions() -> Sequence[RowMapping]:
        query = text("SELECT session_name, account_id, mode, context FROM trading.session_registry")
        with engine.connect() as conn:
            return conn.execute(query).mappings().all()

    @staticmethod
    def fetch_portfolios(account_id: str, only_enabled: bool = True) -> list[dict]:
        query = """
                SELECT portfolio_id, portfolio_name, strategy_id, account_id
                FROM trading.portfolio_registry
                WHERE account_id = :account_id \
                """

        if only_enabled:
            query += " AND enabled = TRUE"

        query = text(query)

        with engine.connect() as conn:
            result = conn.execute(query, {"account_id": account_id})
            portfolios = [dict(row) for row in result.mappings().all()]

        return portfolios



    # @staticmethod
    # def insert_session(session_name: str, account_id: str, mode: str, context: dict | None = None) -> None:
    #     query = text("""
    #         INSERT INTO trading.session_registry (session_name, account_id, mode, context)
    #         VALUES (:session_name, :account_id, :mode, :context)
    #     """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(
    #             query,
    #             {
    #                 "session_name": session_name,
    #                 "account_id": account_id,
    #                 "mode": mode,
    #                 "context": context
    #             }
    #         )

    # @staticmethod
    # def insert_portfolio(
    #     account_id: str,
    #     strategy_id: str,
    #     portfolio_id: str,
    #     portfolio_name: str,
    #     currency: str = "EUR",
    #     enabled: bool = True
    # ) -> None:
    #     query = text("""
    #         INSERT INTO trading.portfolio_registry
    #             (account_id, portfolio_id, portfolio_name, strategy_id, currency, enabled)
    #         VALUES
    #             (:account_id, :portfolio_id, :portfolio_name, :strategy_id, :currency, :enabled)
    #     """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(
    #             query,
    #             {
    #                 "account_id": account_id,
    #                 "portfolio_id": portfolio_id,
    #                 "portfolio_name": portfolio_name,
    #                 "strategy_id": strategy_id,
    #                 "currency": currency,
    #                 "enabled": enabled
    #             }
    #         )


    # @staticmethod
    # def delete_portfolio(account_id: str, portfolio_id: str) -> dict | None:
    #     query = text("""
    #         DELETE FROM trading.portfolio_registry
    #         WHERE account_id = :account_id
    #           AND portfolio_id = :portfolio_id
    #         RETURNING id
    #     """)
    #
    #     with engine.begin() as conn:
    #         result = conn.execute(
    #             query,
    #             {
    #                 "account_id": account_id,
    #                 "portfolio_id": portfolio_id
    #             }
    #         )
    #         deleted = result.mappings().first()
    #
    #     return deleted

    #
    #
    # @staticmethod
    # def fetch_sessions_by_account(account_id: str) -> Sequence[RowMapping]:
    #     query = text("SELECT session_name, account_id, mode, context FROM trading.session_registry WHERE account_id = :account_id")
    #     with engine.connect() as conn:
    #         return conn.execute(query, {"account_id": account_id}).mappings().all()
    #
    #
    # @staticmethod
    # def session_exists_for_account(account_id: str) -> bool:
    #     query = text("""
    #         SELECT 1
    #         FROM trading.session_registry
    #         WHERE account_id = :account_id
    #         LIMIT 1
    #     """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(
    #             query,
    #             {"account_id": account_id}
    #         )
    #         row = result.mappings().first()
    #
    #     return row is not None
    #
    # @staticmethod
    # def exists_for_portfolio(portfolio_id: str) -> bool:
    #     query = text("""
    #         SELECT 1
    #         FROM trading.portfolio_registry
    #         WHERE portfolio_id = :portfolio_id
    #         LIMIT 1
    #     """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(
    #             query,
    #             {"portfolio_id": portfolio_id}
    #         )
    #         row = result.mappings().first()
    #
    #     return row is not None
    #
    # @staticmethod
    # def portfolio_is_enabled(portfolio_id: str) -> bool:
    #     query = text("""
    #         SELECT 1
    #         FROM trading.portfolio_registry
    #         WHERE portfolio_id = :portfolio_id
    #           AND enabled = TRUE
    #         LIMIT 1
    #     """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(
    #             query,
    #             {"portfolio_id": portfolio_id}
    #         )
    #         row = result.mappings().first()
    #
    #     return row is not None
    #
    #
    #
    # @staticmethod
    # def insert_instrument(
    #     symbol: str,
    #     currency: str,
    #     long_name: str | None = None,
    #     sector: str | None = None,
    # ) -> None:
    #
    #     query = text("""
    #         INSERT INTO trading.instruments (symbol, currency, long_name, sector)
    #         VALUES (:symbol, :currency, :long_name, :sector)
    #         RETURNING instrument_id
    #     """)
    #
    #     with engine.begin() as conn:
    #          conn.execute(
    #             query,
    #             {
    #                 "symbol": symbol,
    #                 "currency": currency,
    #                 "long_name": long_name,
    #                 "sector": sector
    #             }
    #         )
    #
    # @staticmethod
    # def insert_contract(contract) -> None:
    #     query = text("""
    #         INSERT INTO trading.contracts (
    #             con_id, instrument_id, symbol, sec_type, exchange, primary_exchange, currency, local_symbol, trading_class
    #         )
    #         VALUES (
    #             :con_id,
    #             (SELECT instrument_id FROM trading.instruments WHERE symbol = :symbol AND currency = :currency),
    #             :symbol, :sec_type, :exchange, :primary_exchange, :currency, :local_symbol, :trading_class
    #         )
    #         ON CONFLICT (con_id) DO NOTHING;
    #     """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(
    #             query,
    #             {
    #                 "con_id": contract.conId,
    #                 "symbol": contract.symbol,
    #                 "sec_type": contract.secType,
    #                 "exchange": contract.exchange,
    #                 "primary_exchange": contract.primaryExchange,
    #                 "currency": contract.currency,
    #                 "local_symbol": contract.localSymbol,
    #                 "trading_class": contract.tradingClass
    #             }
    #         )
    #
    # @staticmethod
    # def fetch_contracts() -> list[dict]:
    #     query = """
    #         SELECT con_id, symbol, sec_type, exchange, primary_exchange, currency
    #         FROM trading.contracts
    #     """
    #     query = text(query)
    #     with engine.connect() as conn:
    #         result = conn.execute(query)
    #         contracts = [dict(row) for row in result.mappings().all()]
    #     return contracts
    #
    #
    # @staticmethod
    # def insert_order(order: "Order", account_id: str, portfolio_id: str, con_id: int) -> None:
    #     query = text("""
    #                  INSERT INTO trading.orders (perm_id, account_id, portfolio_id, con_id, action, order_ref, order_type, tif,
    #                                      quantity,
    #                                      lmt_price, aux_price, status, filled_quantity, remaining_quantity,
    #                                      avg_fill_price,
    #                                      reference_price_type, oca_group, oca_type, created_at, updated_at)
    #                  VALUES (:perm_id, :account_id, :portfolio_id, :con_id, :action, :order_ref, :order_type, :tif,
    #                          :quantity,
    #                          :lmt_price, :aux_price, :status, :filled_quantity, :remaining_quantity, :avg_fill_price,
    #                          :reference_price_type, :oca_group, :oca_type, NOW(), NOW())
    #                  ON CONFLICT (perm_id) DO NOTHING
    #                  """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(
    #             query,
    #             {
    #                 "perm_id": order.permId,
    #                 "account_id": account_id,
    #                 "portfolio_id": portfolio_id,
    #                 "con_id": con_id,
    #                 "action": order.action,
    #                 "order_ref": order.orderRef,
    #                 "order_type": order.orderType,
    #                 "tif": order.tif,
    #                 "quantity": order.totalQuantity,
    #                 "lmt_price": order.lmtPrice if order.lmtPrice <= 1e11 else None,
    #                 "aux_price": order.auxPrice if order.auxPrice <= 1e11 else None,
    #                 "status": "PendingSubmit",
    #                 "filled_quantity": 0.0,
    #                 "remaining_quantity": order.totalQuantity,
    #                 "avg_fill_price": 0.0,
    #                 "reference_price_type": 0 if order.referencePriceType == 2147483647 else order.referencePriceType,
    #                 "oca_group": order.ocaGroup,
    #                 "oca_type": order.ocaType
    #             }
    #         )
    #
    # @staticmethod
    # def order_exists(perm_id: int) -> bool:
    #     query = text("""
    #                  SELECT 1
    #                  FROM trading.orders
    #                  WHERE perm_id = :perm_id
    #                  LIMIT 1
    #                  """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(
    #             query,
    #             {"perm_id": perm_id}
    #         )
    #         row = result.mappings().first()
    #
    #     return row is not None
    #
    # @staticmethod
    # def update_order_status(perm_id: int, status: str, filled_quantity: float, remaining_quantity: float,
    #                         avg_fill_price: float) -> None:
    #     query = text("""
    #                  UPDATE trading.orders
    #                  SET status             = :status,
    #                      filled_quantity    = :filled_quantity,
    #                      remaining_quantity = :remaining_quantity,
    #                      avg_fill_price     = :avg_fill_price,
    #                      updated_at         = NOW()
    #                  WHERE perm_id = :perm_id
    #                  """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(
    #             query,
    #             {
    #                 "perm_id": perm_id,
    #                 "status": status,
    #                 "filled_quantity": filled_quantity,
    #                 "remaining_quantity": remaining_quantity,
    #                 "avg_fill_price": avg_fill_price
    #             }
    #         )
    #
    #
    # @staticmethod
    # def insert_execution(conn : "Connection", execution: "Execution", account_id: str, portfolio_id: str, con_id: int) -> None:
    #     query = text("""
    #         INSERT INTO trading.executions (
    #             exec_id, perm_id, account_id, portfolio_id, con_id,
    #             side, shares, price, execution_time,
    #             cum_qty, avg_price, last_liquidity, pending_price_revision
    #         ) VALUES (
    #             :exec_id, :perm_id, :account_id, :portfolio_id, :con_id,
    #             :side, :shares, :price, :execution_time,
    #             :cum_qty, :avg_price, :last_liquidity, :pending_price_revision
    #         )
    #         ON CONFLICT (exec_id) DO NOTHING
    #     """)
    #
    #     conn.execute(
    #         query,
    #         {
    #             "exec_id": execution.execId,
    #             "perm_id": execution.permId,
    #             "account_id": account_id,
    #             "portfolio_id": portfolio_id,
    #             "con_id": con_id,
    #             "side": execution.side,
    #             "shares": execution.shares,
    #             "price": execution.price,
    #             "execution_time": execution.time,
    #             "cum_qty": execution.cumQty,
    #             "avg_price": execution.avgPrice,
    #             "last_liquidity": execution.lastLiquidity,
    #             "pending_price_revision": execution.pendingPriceRevision,
    #         }
    #     )
    #
    #
    # def _update_lots(self, conn : "Connection", execution, portfolio_id: str, con_id: int) -> None:
    #     side = execution.side  # 'BOT' ou 'SLD'
    #
    #     if side == "BOT":
    #         self._handle_buy(conn, execution, portfolio_id, con_id)
    #
    #     elif side == "SLD":
    #         self._handle_sell(conn, execution, portfolio_id, con_id)
    #
    #     else:
    #         raise ValueError(f"Unsupported execution side: {side}")
    #
    #
    # def _handle_buy(self, conn : "Connection", execution, portfolio_id: str, con_id: int) -> None:
    #     shares = self._D(execution.shares)
    #     price = self._D(execution.price)
    #
    #     self._insert_trade_lot(
    #         conn=conn,
    #         portfolio_id=portfolio_id,
    #         con_id=con_id,
    #         buy_exec_id=execution.execId,
    #         quantity=shares,
    #         price=price,
    #     )
    #
    # @staticmethod
    # def _insert_trade_lot(
    #     conn: "Connection",
    #     portfolio_id: str,
    #     con_id: int,
    #     buy_exec_id: str,
    #     quantity: Decimal,
    #     price: Decimal,
    # ) -> None:
    #     query = text("""
    #         INSERT INTO trading.trade_lots (
    #             portfolio_id,
    #             con_id,
    #             buy_exec_id,
    #             open_quantity,
    #             closed_quantity,
    #             price,
    #             created_at
    #         )
    #         VALUES (:portfolio_id,
    #                 :con_id,
    #                 :buy_exec_id,
    #                 :open_quantity,
    #                 0,
    #                 :price,
    #                 NOW()
    #         )
    #         ON CONFLICT (portfolio_id, buy_exec_id) DO NOTHING
    #
    #
    #     """)
    #
    #     conn.execute(
    #         query,
    #         {
    #             "portfolio_id": portfolio_id,
    #             "con_id": con_id,
    #             "buy_exec_id": buy_exec_id,
    #             "open_quantity": quantity,
    #             "price": price,
    #         },
    #     )
    #
    #
    # def _handle_sell(self, conn : "Connection", execution, portfolio_id: str, con_id: int) -> None:
    #     qty_to_sell = self._D(execution.shares)
    #     sell_price = self._D(execution.price)
    #
    #     lots = self._select_open_lots(
    #         portfolio_id, con_id
    #     )
    #     total_available = sum(self._D(lot.open_quantity) for lot in lots)
    #     if qty_to_sell > total_available:
    #         raise ValueError(
    #             "SELL execution exceeds available open lots (short not supported)"
    #         )
    #
    #     for lot in lots:
    #         if qty_to_sell <= 0:
    #             break
    #
    #         lot_id = lot.id
    #         lot_open = self._D(lot.open_quantity)
    #         lot_price = self._D(lot.price)
    #
    #         consume_qty = min(lot_open, qty_to_sell)
    #         realized_pnl = (sell_price - lot_price) * consume_qty
    #
    #         self._insert_lot_consumption(
    #             conn=conn,
    #             lot_id=lot_id,
    #             sell_exec_id=execution.execId,
    #             quantity=consume_qty,
    #             realized_pnl=realized_pnl,
    #         )
    #
    #         self._update_lot_quantities(
    #             conn=conn,
    #             lot_id=lot_id,
    #             quantity=consume_qty,
    #         )
    #
    #         qty_to_sell -= consume_qty
    #
    #
    # @staticmethod
    # def _select_open_lots(portfolio_id: str, con_id: int):
    #     query = text("""
    #         SELECT id, open_quantity, price
    #         FROM trading.trade_lots
    #         WHERE portfolio_id = :portfolio_id
    #           AND con_id = :con_id
    #           AND open_quantity > 0
    #         ORDER BY id
    #     """)
    #
    #     with engine.begin() as conn:
    #         return conn.execute(
    #             query,
    #             {
    #                 "portfolio_id": portfolio_id,
    #                 "con_id": con_id,
    #             },
    #         ).fetchall()
    #
    # @staticmethod
    # def _insert_lot_consumption(
    #     conn: "Connection",
    #     lot_id: int,
    #     sell_exec_id: str,
    #     quantity: Decimal,
    #     realized_pnl: Decimal,
    # ) -> None:
    #     query = text("""
    #         INSERT INTO trading.trade_lot_consumption (
    #             lot_id,
    #             sell_exec_id,
    #             quantity,
    #             realized_pnl,
    #             created_at
    #         )
    #         VALUES (
    #             :lot_id,
    #             :sell_exec_id,
    #             :quantity,
    #             :realized_pnl,
    #             NOW()
    #         )
    #     """)
    #
    #     conn.execute(
    #         query,
    #         {
    #             "lot_id": lot_id,
    #             "sell_exec_id": sell_exec_id,
    #             "quantity": quantity,
    #             "realized_pnl": realized_pnl,
    #         },
    #     )
    #
    # @staticmethod
    # def _update_lot_quantities(
    #     conn: "Connection",
    #     lot_id: int,
    #     quantity: Decimal,
    # ) -> None:
    #     query = text("""
    #         UPDATE trading.trade_lots
    #         SET open_quantity = open_quantity - :qty,
    #             closed_quantity = closed_quantity + :qty,
    #             updated_at = NOW()
    #         WHERE id = :lot_id
    #     """)
    #
    #     conn.execute(
    #         query,
    #         {
    #             "qty": quantity,
    #             "lot_id": lot_id,
    #         },
    #     )
    #
    # @staticmethod
    # def _insert_position(
    #         conn: "Connection",
    #         portfolio_id: str,
    #         account_id: str,
    #         con_id: int
    # ) -> None:
    #
    #     query_exec = text("""
    #                       SELECT side, shares, price
    #                       FROM trading.executions
    #                       WHERE account_id = :account_id
    #                         AND portfolio_id = :portfolio_id
    #                         AND con_id = :con_id
    #                       ORDER BY execution_time, exec_id
    #                       """)
    #
    #     executions = conn.execute(query_exec, {
    #         "account_id": account_id,
    #         "portfolio_id": portfolio_id,
    #         "con_id": con_id
    #     }).fetchall()
    #
    #     total_qty = Decimal("0.0")
    #     total_cost = Decimal("0.0")
    #     net_qty = Decimal("0.0")
    #
    #     for exec_row in executions:
    #         side = exec_row.side
    #         shares = Decimal(exec_row.shares)
    #         price = Decimal(exec_row.price)
    #
    #         if side == "BOT":
    #             total_qty += shares
    #             total_cost += shares * price
    #             net_qty += shares
    #         elif side == "SLD":
    #             net_qty -= shares
    #             if net_qty < 0:
    #                 raise ValueError("SELL execution exceeds available quantity")
    #
    #     avg_cost = total_cost / total_qty if total_qty > 0 else Decimal("0.0")
    #
    #     if net_qty > 0:
    #         query_upsert = text("""
    #                             INSERT INTO trading.positions(account_id, portfolio_id, con_id, quantity, avg_cost)
    #                             VALUES (:account_id, :portfolio_id, :con_id, :quantity, :avg_cost)
    #                             ON CONFLICT(account_id, portfolio_id, con_id)
    #                                 DO UPDATE SET quantity   = :quantity,
    #                                               avg_cost   = :avg_cost,
    #                                               updated_at = NOW()
    #                             """)
    #         conn.execute(query_upsert, {
    #             "account_id": account_id,
    #             "portfolio_id": portfolio_id,
    #             "con_id": con_id,
    #             "quantity": net_qty,
    #             "avg_cost": avg_cost
    #         })
    #     else:
    #         query_delete = text("""
    #                             DELETE
    #                             FROM trading.positions
    #                             WHERE account_id = :account_id
    #                               AND portfolio_id = :portfolio_id
    #                               AND con_id = :con_id
    #                             """)
    #         conn.execute(query_delete, {
    #             "account_id": account_id,
    #             "portfolio_id": portfolio_id,
    #             "con_id": con_id
    #         })
    #
    # @staticmethod
    # def fetch_positions(portfolio_id: str) -> list[dict]:
    #     query = text("""
    #                  SELECT p.account_id,
    #                         p.portfolio_id,
    #                         p.con_id,
    #                         c.symbol,
    #                         p.quantity,
    #                         p.avg_cost,
    #                         p.market_price,
    #                         p.market_value,
    #                         p.unrealized_pnl,
    #                         p.updated_at
    #                  FROM trading.positions p
    #                           JOIN trading.contracts c
    #                                ON p.con_id = c.con_id
    #                  WHERE p.portfolio_id = :portfolio_id
    #                  """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(query, {"portfolio_id": portfolio_id})
    #         return [dict(row) for row in result.mappings().all()]
    #
    #
    # @staticmethod
    # def _get_realized_pnl_from_fifo(conn: "Connection", exec_id: int) -> Decimal:
    #     query = text("""
    #                  SELECT COALESCE(SUM(realized_pnl), 0)
    #                  FROM trading.trade_lot_consumption
    #                  WHERE sell_exec_id = :exec_id
    #                  """)
    #
    #     pnl = conn.execute(query, {"exec_id": exec_id}).scalar_one()
    #
    #     return Decimal(pnl)
    #
    #
    # def _build_ledger_entries(
    #         self,
    #         conn: "Connection",
    #         execution,
    #         con_id: int,
    #         commission: Optional["CommissionReport"] = None,
    # ) -> list[dict]:
    #
    #     side = execution.side
    #     shares = Decimal(execution.shares)
    #     price = Decimal(execution.price)
    #     exec_id = execution.execId
    #     currency = commission.currency if commission else "USD"
    #
    #     entries: list[dict] = []
    #
    #     if side == "BOT":
    #         entries.append({
    #             "type": "TRADE_DEBIT",
    #             "amount": self._quantize(shares * price),
    #             "con_id": con_id,
    #             "exec_id": exec_id,
    #             "currency": currency,
    #         })
    #
    #         if commission:
    #             entries.append({
    #                 "type": "COMMISSION",
    #                 "amount": Decimal(commission.commission),
    #                 "con_id": con_id,
    #                 "exec_id": exec_id,
    #                 "currency": commission.currency,
    #             })
    #
    #     elif side == "SLD":
    #         entries.append({
    #             "type": "TRADE_CREDIT",
    #             "amount": self._quantize(shares * price),
    #             "con_id": con_id,
    #             "exec_id": exec_id,
    #             "currency": currency,
    #         })
    #
    #         pnl = self._get_realized_pnl_from_fifo(conn, exec_id)
    #
    #         if pnl != Decimal("0"):
    #             entries.append({
    #                 "type": "REALIZED_PNL",
    #                 "amount": pnl,
    #                 "con_id": con_id,
    #                 "exec_id": exec_id,
    #                 "currency": currency,
    #             })
    #
    #         if commission:
    #             entries.append({
    #                 "type": "COMMISSION",
    #                 "amount": Decimal(commission.commission),
    #                 "con_id": con_id,
    #                 "exec_id": exec_id,
    #                 "currency": commission.currency,
    #             })
    #
    #     else:
    #         raise ValueError(f"Unsupported execution side: {side}")
    #
    #     return entries
    #
    # def update_portfolio_ledger(
    #         self,
    #         conn: "Connection",
    #         execution,
    #         account_id: str,
    #         portfolio_id: str,
    #         con_id: int,
    #         commission: Optional["CommissionReport"] = None,
    # ) -> None:
    #
    #     entries = self._build_ledger_entries(
    #         conn,
    #         execution,
    #         con_id,
    #         commission,
    #     )
    #
    #     query = text("""
    #                  INSERT INTO trading.portfolio_ledger (account_id,
    #                                                portfolio_id,
    #                                                con_id,
    #                                                exec_id,
    #                                                type,
    #                                                amount,
    #                                                currency,
    #                                                created_at)
    #                  VALUES (:account_id,
    #                          :portfolio_id,
    #                          :con_id,
    #                          :exec_id,
    #                          :type,
    #                          :amount,
    #                          :currency,
    #                          NOW())
    #                  ON CONFLICT (exec_id, type) DO NOTHING
    #                  """)
    #
    #     for entry in entries:
    #         if entry["type"] == "COMMISSION" and entry["amount"] == 0:
    #             continue
    #         currency = entry.get("currency") or "USD"
    #
    #         conn.execute(query, {
    #             "account_id": account_id,
    #             "portfolio_id": portfolio_id,
    #             "con_id": entry["con_id"],
    #             "exec_id": entry["exec_id"],
    #             "type": entry["type"],
    #             "amount": entry["amount"],
    #             "currency": currency,
    #         })
    #
    #
    # def update_order_in_db(
    #         self,
    #         trade: "Trade",
    #         perm_id: int,
    #         portfolio_id: str,
    #         account_id: str
    # ):
    #     order_status = trade.orderStatus
    #     order = trade.order
    #     contract = trade.contract
    #
    #     if not self.order_exists(perm_id):
    #         self.insert_order(
    #             order=order,
    #             portfolio_id=portfolio_id,
    #             account_id=account_id,
    #             con_id=contract.conId
    #         )
    #
    #     self.update_order_status(
    #         perm_id=perm_id,
    #         status=order_status.status,
    #         filled_quantity=order_status.filled,
    #         remaining_quantity=order_status.remaining,
    #         avg_fill_price=order_status.avgFillPrice
    #     )
    #
    #     if order_status.status in ("Cancelled", "Inactive", "ApiCancelled"):
    #         self.update_order_status(
    #             perm_id=perm_id,
    #             status=order_status.status,
    #             filled_quantity=order_status.filled,
    #             remaining_quantity=order_status.remaining,
    #             avg_fill_price=order_status.avgFillPrice
    #         )
    #
    #         #TODO:LOW retry_order(order_id) add cancelOrder()
    #
    # def update_fill_in_db(
    #         self,
    #         execution,
    #         fill,
    #         account_id: str,
    #         portfolio_id: str,
    #         con_id: int
    # ):
    #     with UnitOfWork() as conn:
    #         self.insert_execution(
    #             conn=conn,
    #             execution=execution,
    #             account_id=account_id,
    #             portfolio_id=portfolio_id,
    #             con_id=con_id
    #         )
    #
    #         self._update_lots(
    #             conn=conn,
    #             execution=execution,
    #             portfolio_id=portfolio_id,
    #             con_id=con_id
    #         )
    #
    #         self._insert_position(
    #             conn=conn,
    #             portfolio_id=portfolio_id,
    #             account_id=account_id,
    #             con_id=con_id
    #         )
    #
    #         self.update_portfolio_ledger(
    #             conn=conn,
    #             execution=execution,
    #             commission=getattr(fill, "commissionReport", None),
    #             account_id=account_id,
    #             portfolio_id=portfolio_id,
    #             con_id=con_id
    #         )
    #
    #
    # def update_commission_in_db(
    #     self,
    #     *,
    #     execution,
    #     commission,
    #     account_id: str,
    #     portfolio_id: str,
    #     con_id: int
    # ):
    #
    #     with UnitOfWork() as conn:
    #         self.update_portfolio_ledger(
    #             conn=conn,
    #             execution=execution,
    #             commission=commission,
    #             account_id=account_id,
    #             portfolio_id=portfolio_id,
    #             con_id=con_id
    #         )
    #
    #
    # @staticmethod
    # def fetch_instruments() -> list[dict]:
    #     query = """
    #         SELECT
    #             c.con_id,
    #             c.symbol,
    #             c.sec_type,
    #             c.exchange,
    #             c.primary_exchange,
    #             c.currency,
    #             i.long_name,
    #             i.sector
    #         FROM trading.contracts c
    #         LEFT JOIN trading.instruments i
    #             ON c.instrument_id = i.instrument_id
    #     """
    #     query = text(query)
    #     with engine.connect() as conn:
    #         result = conn.execute(query)
    #         contracts = [dict(row) for row in result.mappings().all()]
    #     return contracts

    #
    # @staticmethod
    # def insert_portfolio_target(
    #         account_id: str,
    #         portfolio_id: str,
    #         strategy_id: str,
    #         rebalance_date: str,  # format 'YYYY-MM-DD'
    #         weights: dict[int, float],  # {instrument_id: target_weight}
    #         tolerance: float = 0.02
    # ) -> None:
    #
    #     insert_target_query = text("""
    #                                INSERT INTO trading.portfolio_targets (account_id, portfolio_id, strategy_id, rebalance_date, tolerance)
    #                                VALUES (:account_id, :portfolio_id, :strategy_id, :rebalance_date, :tolerance)
    #                                ON CONFLICT (account_id, portfolio_id, rebalance_date)
    #                                    DO UPDATE SET strategy_id = EXCLUDED.strategy_id,
    #                                                  tolerance   = EXCLUDED.tolerance,
    #                                                  created_at  = NOW()
    #                                RETURNING target_id
    #                                """)
    #
    #     with engine.begin() as conn:
    #         target_id = conn.execute(
    #             insert_target_query,
    #             {
    #                 "account_id": account_id,
    #                 "portfolio_id": portfolio_id,
    #                 "strategy_id": strategy_id,
    #                 "rebalance_date": rebalance_date,
    #                 "tolerance": tolerance
    #             }
    #         ).scalar()
    #
    #         delete_weights_query = text("DELETE FROM trading.portfolio_target_weights WHERE target_id = :target_id")
    #         conn.execute(delete_weights_query, {"target_id": target_id})
    #
    #         if weights:
    #             insert_weight_query = text("""
    #                                        INSERT INTO trading.portfolio_target_weights (target_id, con_id, target_weight)
    #                                        VALUES (:target_id, :con_id, :target_weight)
    #                                        """)
    #             weight_rows = [
    #                 {"target_id": target_id, "con_id": con_id, "target_weight": weight}
    #                 for con_id, weight in weights.items()
    #             ]
    #
    #             conn.execute(insert_weight_query, weight_rows)

    # @staticmethod
    # def fetch_portfolio_targets(portfolio_id: str, rebalance_date: str) -> list[dict]:
    #     query = text("""
    #         SELECT t.target_id, t.rebalance_date, t.tolerance,
    #                w.con_id, w.target_weight
    #         FROM trading.portfolio_targets t
    #         JOIN trading.portfolio_target_weights w ON t.target_id = w.target_id
    #         WHERE t.portfolio_id = :portfolio_id
    #           AND t.rebalance_date = :rebalance_date
    #     """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(query, {"portfolio_id": portfolio_id, "rebalance_date": rebalance_date})
    #         return [dict(row) for row in result.mappings().all()]
    #
    # @staticmethod
    # def check_rebalance_date(portfolio_id: str, today: datetime) -> bool:
    #     query = text("""
    #                  SELECT 1
    #                  FROM trading.portfolio_targets
    #                  WHERE portfolio_id = :portfolio_id
    #                    AND rebalance_date = :today
    #                  LIMIT 1
    #                  """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(query, {"portfolio_id": portfolio_id, "today": today}).fetchone()
    #         return result is not None

    #
    # @staticmethod
    # def _update_margin_account(state: "AccountState", currency: str):
    #     m = state.margin
    #     if not m:
    #         return
    #
    #     query = text("""
    #         INSERT INTO trading.account_margins (
    #             account_id, currency, equity_with_loan, full_available_funds, full_excess_liquidity,
    #             full_init_margin_req, full_maint_margin_req, gross_position_value, net_liquidation,
    #             total_cash_value, buying_power, cushion, lookahead_next_change, updated_at
    #         )
    #         VALUES (
    #             :account_id, :currency, :equity_with_loan, :full_available_funds, :full_excess_liquidity,
    #             :full_init_margin_req, :full_maint_margin_req, :gross_position_value, :net_liquidation,
    #             :total_cash_value, :buying_power, :cushion, :lookahead_next_change, NOW()
    #         )
    #         ON CONFLICT (account_id, currency)
    #         DO UPDATE SET
    #             equity_with_loan        = EXCLUDED.equity_with_loan,
    #             full_available_funds    = EXCLUDED.full_available_funds,
    #             full_excess_liquidity   = EXCLUDED.full_excess_liquidity,
    #             full_init_margin_req    = EXCLUDED.full_init_margin_req,
    #             full_maint_margin_req   = EXCLUDED.full_maint_margin_req,
    #             gross_position_value    = EXCLUDED.gross_position_value,
    #             net_liquidation         = EXCLUDED.net_liquidation,
    #             total_cash_value        = EXCLUDED.total_cash_value,
    #             buying_power            = EXCLUDED.buying_power,
    #             cushion                 = EXCLUDED.cushion,
    #             lookahead_next_change   = EXCLUDED.lookahead_next_change,
    #             updated_at              = NOW()
    #     """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(query, {
    #             "account_id": state.account,
    #             "currency": currency,
    #             "equity_with_loan": m.equity_with_loan,
    #             "full_available_funds": m.full_available_funds,
    #             "full_excess_liquidity": m.full_excess_liquidity,
    #             "full_init_margin_req": m.full_init_margin_req,
    #             "full_maint_margin_req": m.full_maint_margin_req,
    #             "gross_position_value": state.gross_position_value,
    #             "net_liquidation": state.net_liquidation,
    #             "total_cash_value": state.total_cash_value,
    #             "buying_power": m.buying_power,
    #             "cushion": m.cushion,
    #             "lookahead_next_change": m.lookahead_next_change
    #         })

    # @staticmethod
    # def _update_balance_account(state: "AccountState", currency: str):
    #     b = state.balances.get(currency)
    #     if not b:
    #         return
    #
    #     query = text("""
    #                  INSERT INTO trading.account_balances (account_id, currency, total_cash_balance, accrued_cash,
    #                                                net_liquidation_by_currency,
    #                                                stock_market_value, unrealized_pnl, exchange_rate,
    #                                                net_dividend, updated_at)
    #                  VALUES (:account_id, :currency, :total_cash_balance, :accrued_cash, :net_liquidation_by_currency,
    #                          :stock_market_value, :unrealized_pnl, :exchange_rate, :net_dividend, NOW())
    #                  ON CONFLICT (account_id, currency)
    #                      DO UPDATE SET total_cash_balance          = EXCLUDED.total_cash_balance,
    #                                    accrued_cash                = EXCLUDED.accrued_cash,
    #                                    net_liquidation_by_currency = EXCLUDED.net_liquidation_by_currency,
    #                                    stock_market_value          = EXCLUDED.stock_market_value,
    #                                    unrealized_pnl              = EXCLUDED.unrealized_pnl,
    #                                    exchange_rate               = EXCLUDED.exchange_rate,
    #                                    net_dividend                = EXCLUDED.net_dividend,
    #                                    updated_at                  = NOW()
    #                  """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(query, {
    #             "account_id": state.account,
    #             "currency": currency,
    #             "total_cash_balance": b.total_cash_balance,
    #             "accrued_cash": b.accrued_cash,
    #             "net_liquidation_by_currency": b.net_liquidation_by_currency,
    #             "stock_market_value": b.stock_market_value,
    #             "unrealized_pnl": b.unrealized_pnl,
    #             "realized_pnl": b.realized_pnl,
    #             "exchange_rate": b.exchange_rate,
    #             "net_dividend": b.net_dividend
    #         })

    #
    # def update_account_state_in_db(self, state: "AccountState"):
    #     if not state.account:
    #         raise ValueError("AccountState must have an account_id")
    #
    #     self._update_margin_account(state, "USD")
    #
    #     for currency in state.balances.keys():
    #         self._update_balance_account(state, currency)

    #
    # @staticmethod
    # def get_account_total_cash(account_id: str, currency: str = "USD") -> Optional[Decimal]:
    #     query = text("""
    #                  SELECT total_cash_balance
    #                  FROM trading.account_balances
    #                  WHERE account_id = :account_id
    #                    AND currency = :currency
    #                  LIMIT 1
    #                  """)
    #
    #     with engine.begin() as conn:
    #         result = conn.execute(query, {"account_id": account_id, "currency": currency}).scalar_one_or_none()
    #
    #     return Decimal(result) if result is not None else None


    # def insert_capital_event(
    #         self,
    #         account_id: str,
    #         portfolio_id: str,
    #         event: str,
    #         amount: Decimal,
    #         currency: str = "USD"
    # ):
    #     if event not in ("INITIAL_CAPITAL", "CAPITAL_ADDITION", "CAPITAL_WITHDRAWAL"):
    #         raise ValueError(f"Unsupported capital type: {event}")
    #
    #     amount = self._quantize(amount)
    #
    #     query = text("""
    #                  INSERT INTO trading.portfolio_capital (account_id, portfolio_id, type, amount, currency, created_at)
    #                  VALUES (:account_id, :portfolio_id, :type, :amount, :currency, NOW())
    #                  ON CONFLICT (portfolio_id, type, created_at) DO NOTHING
    #                  """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(query, {
    #             "account_id": account_id,
    #             "portfolio_id": portfolio_id,
    #             "type": event,
    #             "amount": amount,
    #             "currency": currency,
    #         })


    # def update_portfolio_balances(
    #         self,
    #         portfolio_id: str,
    #         account_id: str,
    #         currency: str = "USD"
    # ) -> None:
    #
    #     query = text("""
    #                  WITH capital AS (SELECT portfolio_id,
    #                                          COALESCE(SUM(
    #                                                           CASE
    #                                                               WHEN type = 'INITIAL_CAPITAL' THEN amount
    #                                                               WHEN type = 'CAPITAL_ADDITION' THEN amount
    #                                                               WHEN type = 'CAPITAL_WITHDRAWAL' THEN -amount
    #                                                               END
    #                                                   ), 0) AS capital_cash
    #                                   FROM trading.portfolio_capital
    #                                   WHERE portfolio_id = :portfolio_id
    #                                   GROUP BY portfolio_id),
    #                       ledger AS (SELECT portfolio_id,
    #                                         COALESCE(SUM(
    #                                                          CASE
    #                                                              WHEN type = 'TRADE_CREDIT' THEN amount
    #                                                              WHEN type = 'TRADE_DEBIT' THEN -amount
    #                                                              WHEN type = 'COMMISSION' THEN -amount
    #                                                              END
    #                                                  ), 0)                                                    AS ledger_cash,
    #                                         COALESCE(SUM(CASE WHEN type = 'REALIZED_PNL' THEN amount END), 0) AS realized_pnl,
    #                                         COALESCE(SUM(CASE WHEN type = 'COMMISSION' THEN amount END), 0)   AS total_commissions
    #                                  FROM trading.portfolio_ledger
    #                                  WHERE portfolio_id = :portfolio_id
    #                                  GROUP BY portfolio_id)
    #                  SELECT COALESCE(c.capital_cash, 0) + COALESCE(l.ledger_cash, 0) AS total_cash_balance,
    #                         COALESCE(l.realized_pnl, 0)                              AS realized_pnl,
    #                         COALESCE(l.total_commissions, 0)                         AS total_commissions
    #                  FROM capital c
    #                           FULL JOIN ledger l USING (portfolio_id)
    #                  """)
    #
    #     with engine.begin() as conn:
    #         r = conn.execute(query, {"portfolio_id": portfolio_id}).one()
    #
    #         params = {
    #             "portfolio_id": portfolio_id,
    #             "account_id": account_id,
    #             "currency": currency,
    #             "total_cash_balance": self._quantize(r.total_cash_balance),
    #             "realized_pnl": self._quantize(r.realized_pnl),
    #             "total_commissions": self._quantize(r.total_commissions),
    #         }
    #
    #         upsert = text("""
    #                       INSERT INTO trading.portfolio_balances (portfolio_id, account_id, currency,
    #                                                       total_cash_balance, realized_pnl, total_commissions,
    #                                                       updated_at)
    #                       VALUES (:portfolio_id, :account_id, :currency,
    #                               :total_cash_balance, :realized_pnl, :total_commissions, NOW())
    #                       ON CONFLICT (portfolio_id)
    #                           DO UPDATE SET total_cash_balance = EXCLUDED.total_cash_balance,
    #                                         realized_pnl       = EXCLUDED.realized_pnl,
    #                                         total_commissions  = EXCLUDED.total_commissions,
    #                                         updated_at         = NOW()
    #                       """)
    #
    #         conn.execute(upsert, params)


    # @staticmethod
    # def get_portfolio_balance(portfolio_id: str, account_id: str, currency: str = "USD") -> dict:
    #     query = text("""
    #                  SELECT total_cash_balance, stock_market_value, unrealized_pnl
    #                  FROM trading.portfolio_balances
    #                  WHERE portfolio_id = :portfolio_id
    #                    AND account_id = :account_id
    #                    AND currency = :currency
    #                  LIMIT 1
    #                  """)
    #
    #     with engine.begin() as conn:
    #         result = conn.execute(query, {
    #             "portfolio_id": portfolio_id,
    #             "account_id": account_id,
    #             "currency": currency
    #         }).first()
    #
    #     if result is None:
    #         return {
    #             "total_cash_balance": Decimal("0"),
    #             "stock_market_value": Decimal("0"),
    #             "unrealized_pnl": Decimal("0")
    #         }
    #
    #     total_cash_balance, stock_market_value, unrealized_pnl = result
    #     return {
    #         "total_cash_balance": Decimal(total_cash_balance),
    #         "stock_market_value": Decimal(stock_market_value),
    #         "unrealized_pnl": Decimal(unrealized_pnl)
    #     }
    #
    #
    # def update_portfolio_in_db(self, portfolio: "Portfolio") -> None:
    #     with UnitOfWork() as conn:
    #         self._update_positions(conn, portfolio)
    #         self._update_portfolio_market_values(conn, portfolio)
    #
    # @staticmethod
    # def _update_positions(conn, portfolio: Portfolio) -> None:
    #     query = text("""
    #                  UPDATE trading.positions
    #                  SET market_price   = :market_price,
    #                      market_value   = :market_value,
    #                      unrealized_pnl = :unrealized_pnl,
    #                      updated_at     = NOW()
    #                  WHERE account_id = :account_id
    #                    AND portfolio_id = :portfolio_id
    #                    AND con_id = :con_id
    #                    AND :market_price IS NOT NULL
    #                    AND :market_price <> -1
    #                  """)
    #
    #     for con_id, pos in portfolio.iter_db_positions():
    #         conn.execute(
    #             query,
    #             {
    #                 "account_id": portfolio.account_id,
    #                 "portfolio_id": portfolio.portfolio_id,
    #                 "con_id": con_id,
    #                 "market_price": pos.market_price,
    #                 "market_value": pos.market_value,
    #                 "unrealized_pnl": pos.unrealized_pnl,
    #             },
    #         )
    #
    #
    # @staticmethod
    # def _update_portfolio_market_values(
    #         conn,
    #         portfolio: "Portfolio"
    # ) -> None:
    #
    #     query = text("""
    #                  UPDATE trading.portfolio_balances
    #                  SET stock_market_value = :stock_market_value,
    #                      unrealized_pnl     = :unrealized_pnl,
    #                      updated_at         = NOW()
    #                  WHERE account_id = :account_id
    #                    AND portfolio_id = :portfolio_id
    #                  """)
    #
    #     conn.execute(
    #         query,
    #         {
    #             "account_id": portfolio.account_id,
    #             "portfolio_id": portfolio.portfolio_id,
    #             "stock_market_value": portfolio.balance.stock_market_value,
    #             "unrealized_pnl": portfolio.balance.unrealized_pnl
    #         }
    #     )
    #
    #
    # @staticmethod
    # def model_is_enabled(model_name: str, version: float) -> bool:
    #     query = text("""
    #                  SELECT 1
    #                  FROM trading.models_registry
    #                  WHERE model_name = :model_name
    #                    AND version = :version
    #                    AND enabled = TRUE
    #                  LIMIT 1
    #                  """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(
    #             query,
    #             {"model_name": model_name, "version": version}
    #         )
    #         row = result.mappings().first()
    #
    #     return row is not None


    # @staticmethod
    # def update_portfolio_model(
    #         portfolio_id: str,
    #         model_name: str,
    #         model_type: str,
    #         version: float
    # ) -> None:
    #
    #     query = text("""
    #                  INSERT INTO trading.portfolio_models (portfolio_id,
    #                                                model_type,
    #                                                model_name,
    #                                                version,
    #                                                created_at,
    #                                                updated_at)
    #                  VALUES (:portfolio_id,
    #                          :model_type,
    #                          :model_name,
    #                          :version,
    #                          NOW(),
    #                          NOW())
    #                  ON CONFLICT (portfolio_id, model_type)
    #                      DO UPDATE SET model_name = EXCLUDED.model_name,
    #                                    version    = EXCLUDED.version,
    #                                    updated_at = NOW()
    #                  """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(query, {
    #             "portfolio_id": portfolio_id,
    #             "model_type": model_type,
    #             "model_name": model_name,
    #             "version": version
    #         })

    #
    # @staticmethod
    # def update_forecast_model(
    #         model_name: str,
    #         model_type: str,
    #         version: float,
    #         path: str,
    #         description: str | None,
    #         enabled: bool
    # ) -> None:
    #
    #     query = text("""
    #                  INSERT INTO trading.models_registry (model_name,
    #                                               model_type,
    #                                               version,
    #                                               path,
    #                                               description,
    #                                               enabled,
    #                                               created_at,
    #                                               updated_at)
    #                  VALUES (:model_name,
    #                          :model_type,
    #                          :version,
    #                          :path,
    #                          :description,
    #                          :enabled,
    #                          NOW(),
    #                          NOW())
    #                  ON CONFLICT (model_name, version)
    #                      DO UPDATE SET model_type  = EXCLUDED.model_type,
    #                                    path        = EXCLUDED.path,
    #                                    description = EXCLUDED.description,
    #                                    enabled     = EXCLUDED.enabled,
    #                                    updated_at  = NOW()
    #                  """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(query, {
    #             "model_name": model_name,
    #             "model_type": model_type,
    #             "version": version,
    #             "path": path,
    #             "description": description,
    #             "enabled": enabled
    #         })

    # @staticmethod
    # def get_forecast_models_configs() -> List[Dict[str, Any]]:
    #     query = text("""
    #                  SELECT mr.model_name,
    #                         mr.version,
    #                         mr.model_type,
    #                         mr.path,
    #                         mr.description,
    #                         pm.portfolio_id
    #                  FROM trading.models_registry mr
    #                           LEFT JOIN trading.portfolio_models pm
    #                                     ON mr.model_name = pm.model_name
    #                                         AND mr.version = pm.version
    #                  WHERE mr.enabled = TRUE
    #                  ORDER BY pm.portfolio_id NULLS LAST, mr.model_type, mr.model_name
    #                  """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(query)
    #         rows = result.mappings().all()
    #
    #     return [dict(row) for row in rows]

    # @staticmethod
    # def fetch_positions_and_targets(today: str) -> list[dict]:
    #     query = text("""
    #                  WITH portfolio_totals AS (SELECT account_id,
    #                                                   portfolio_id,
    #                                                   SUM(market_value) AS total_value
    #                                            FROM trading.positions
    #                                            GROUP BY account_id, portfolio_id),
    #                       positions_with_weight AS (SELECT p.account_id,
    #                                                        sr.mode AS session_mode,
    #                                                        p.portfolio_id,
    #                                                        p.con_id,
    #                                                        c.symbol,
    #                                                        p.market_value,
    #                                                        pt.total_value,
    #                                                        CASE
    #                                                            WHEN pt.total_value > 0
    #                                                                THEN p.market_value / pt.total_value
    #                                                            ELSE 0
    #                                                            END AS pos_w
    #                                                 FROM trading.positions p
    #                                                          JOIN trading.contracts c ON p.con_id = c.con_id
    #                                                          JOIN trading.session_registry sr ON p.account_id = sr.account_id
    #                                                          JOIN portfolio_totals pt
    #                                                               ON p.account_id = pt.account_id
    #                                                                   AND p.portfolio_id = pt.portfolio_id),
    #                       targets_only AS (SELECT t.account_id,
    #                                               sr.mode         AS session_mode,
    #                                               t.portfolio_id,
    #                                               w.con_id,
    #                                               c.symbol,
    #                                               w.target_weight AS target_w
    #                                        FROM trading.portfolio_targets t
    #                                                 JOIN trading.portfolio_target_weights w ON t.target_id = w.target_id
    #                                                 JOIN trading.contracts c ON w.con_id = c.con_id
    #                                                 JOIN trading.session_registry sr ON t.account_id = sr.account_id
    #                                        WHERE t.rebalance_date = :today),
    #                       combined AS (
    #                           -- positions existantes (avec target si elle existe)
    #                           SELECT pw.account_id,
    #                                  pw.session_mode,
    #                                  pw.portfolio_id,
    #                                  pw.con_id,
    #                                  pw.symbol,
    #                                  pw.pos_w,
    #                                  tw.target_weight AS target_w
    #                           FROM positions_with_weight pw
    #                                    LEFT JOIN trading.portfolio_targets t
    #                                              ON pw.account_id = t.account_id
    #                                                  AND pw.portfolio_id = t.portfolio_id
    #                                                  AND t.rebalance_date = :today
    #                                    LEFT JOIN trading.portfolio_target_weights tw
    #                                              ON t.target_id = tw.target_id
    #                                                  AND pw.con_id = tw.con_id
    #
    #                           UNION ALL
    #
    #                           -- titres qui n'ont pas de position mais existent dans les targets
    #                           SELECT t.account_id,
    #                                  t.session_mode,
    #                                  t.portfolio_id,
    #                                  t.con_id,
    #                                  t.symbol,
    #                                  NULL::NUMERIC AS pos_w,
    #                                  t.target_w
    #                           FROM targets_only t
    #                                    LEFT JOIN positions_with_weight pw
    #                                              ON pw.account_id = t.account_id
    #                                                  AND pw.portfolio_id = t.portfolio_id
    #                                                  AND pw.con_id = t.con_id
    #                           WHERE pw.con_id IS NULL)
    #
    #                  SELECT account_id,
    #                         session_mode,
    #                         portfolio_id,
    #                         con_id,
    #                         symbol,
    #                         pos_w,
    #                         target_w,
    #                         CASE
    #                             WHEN target_w IS NOT NULL AND pos_w IS NULL THEN 'BUY'
    #                             WHEN target_w IS NULL AND pos_w IS NOT NULL
    #                                 AND NOT EXISTS (SELECT 1
    #                                                 FROM trading.portfolio_targets t2
    #                                                 WHERE t2.account_id = combined.account_id
    #                                                   AND t2.portfolio_id = combined.portfolio_id
    #                                                   AND t2.rebalance_date = :today) THEN 'HOLD'
    #                             WHEN target_w IS NULL AND pos_w IS NOT NULL THEN 'SELL'
    #                             WHEN pos_w < target_w THEN 'BUY'
    #                             WHEN pos_w > target_w THEN 'SELL'
    #                             ELSE 'HOLD'
    #                             END AS action
    #                  FROM combined
    #                  ORDER BY portfolio_id, con_id
    #                  """)
    #
    #     with engine.connect() as conn:
    #         rows = conn.execute(query, {"today": today}).mappings().all()
    #         return [dict(row) for row in rows]
    #
    # @staticmethod
    # def persist_model_records(records: list[dict]) -> None:
    #     if not records:
    #         return
    #
    #     query = """
    #             INSERT INTO trading.model_records
    #             (model_name, version, con_id, step, decision, score, output_at, prediction_ts, trading_day)
    #             VALUES (:model_name, :version, :con_id, :step, :decision, :score, :output_at, :prediction_ts, :trading_day)
    #             ON CONFLICT (model_name, version, con_id, trading_day, step) DO NOTHING
    #             """
    #
    #     with UnitOfWork() as conn:
    #         conn.execute(text(query), records)
    #
    # @staticmethod
    # def persist_bars(bars_dict: dict[int, dict[str, Any]]) -> None:
    #     if not bars_dict:
    #         return
    #
    #     rows = []
    #
    #     excluded_values = {-1, None}
    #
    #     for instrument_id, ohlc_dict in bars_dict.items():
    #         last = ohlc_dict['last']
    #         bid = ohlc_dict['bid']
    #         ask = ohlc_dict['ask']
    #
    #         row_data = {
    #             "instrument_id": instrument_id,
    #             "ts_start": last.ts_start,
    #             "ts_end": last.ts_end,
    #             "last_open": last.open,
    #             "last_high": last.high,
    #             "last_low": last.low,
    #             "last_close": last.close,
    #             "last_volume": last.volume,
    #             "last_tick_count": last.tick_count,
    #             "bid_open": bid.open,
    #             "bid_high": bid.high,
    #             "bid_low": bid.low,
    #             "bid_close": bid.close,
    #             "bid_volume": bid.volume,
    #             "bid_tick_count": bid.tick_count,
    #             "ask_open": ask.open,
    #             "ask_high": ask.high,
    #             "ask_low": ask.low,
    #             "ask_close": ask.close,
    #             "ask_volume": ask.volume,
    #             "ask_tick_count": ask.tick_count,
    #         }
    #
    #         if not any(value in excluded_values for value in row_data.values()):
    #             rows.append(row_data)
    #
    #     if not rows:
    #         return
    #
    #     insert_sql = """
    #                  INSERT INTO market.ohlcv_5s (instrument_id, ts_start, ts_end,
    #                                               last_open, last_high, last_low, last_close, last_volume,
    #                                               last_tick_count,
    #                                               bid_open, bid_high, bid_low, bid_close, bid_volume, bid_tick_count,
    #                                               ask_open, ask_high, ask_low, ask_close, ask_volume, ask_tick_count)
    #                  VALUES (:instrument_id,
    #                          to_timestamp(:ts_start),
    #                          to_timestamp(:ts_end),
    #                          :last_open, :last_high, :last_low, :last_close, :last_volume, :last_tick_count,
    #                          :bid_open, :bid_high, :bid_low, :bid_close, :bid_volume, :bid_tick_count,
    #                          :ask_open, :ask_high, :ask_low, :ask_close, :ask_volume, :ask_tick_count)
    #                  ON CONFLICT (instrument_id, ts_start) DO NOTHING
    #                  """
    #
    #     with UnitOfWork() as conn:
    #         conn.execute(text(insert_sql), rows)
    #
    #
    # @staticmethod
    # def feature_exists(uid: str) -> bool:
    #     query = text("""
    #         SELECT 1
    #         FROM trading.feature_registry
    #         WHERE uid = :uid
    #         LIMIT 1
    #     """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(query, {"uid": uid})
    #         row = result.mappings().first()
    #
    #     return row is not None

    #
    # @staticmethod
    # def insert_feature(
    #     uid: str,
    #     category: str,
    #     plugin: str,
    #     scope: str,
    #     kind: str,
    #     fields: str,
    #     freqs: list[str],
    #     params: dict,
    #     priority: int,
    #     cache: bool = False,
    #     is_active: bool = True
    # ) -> None:
    #
    #     query = text("""
    #         INSERT INTO trading.feature_registry (
    #             uid,
    #             category,
    #             plugin,
    #             scope,
    #             kind,
    #             fields,
    #             freqs,
    #             params,
    #             priority,
    #             cache,
    #             is_active
    #         ) VALUES (
    #             :uid,
    #             :category,
    #             :plugin,
    #             :scope,
    #             :kind,
    #             :fields,
    #             CAST(:freqs AS jsonb),
    #             CAST(:params AS jsonb),
    #             :priority,
    #             :cache,
    #             :is_active
    #         )
    #     """)
    #
    #     with engine.begin() as conn:
    #         conn.execute(query, {
    #             "uid": uid,
    #             "category": category,
    #             "plugin": plugin,
    #             "scope": scope,
    #             "kind": kind,
    #             "fields": fields,
    #             "freqs": json.dumps(freqs),
    #             "params": json.dumps(params),
    #             "priority": priority,
    #             "cache": cache,
    #             "is_active": is_active
    #         })


    # @staticmethod
    # def update_feature_status(uid: str, is_active: bool) -> None:
    #     query = text("UPDATE trading.feature_registry SET is_active = :is_active WHERE uid = :uid")
    #
    #     with engine.begin() as conn:
    #         conn.execute(query, {"uid": uid, "is_active": is_active})



    # @staticmethod
    # def get_features_config() -> List[Dict[str, Any]]:
    #     query = text("""
    #         SELECT
    #             category,
    #             plugin,
    #             scope,
    #             kind,
    #             fields,
    #             freqs,
    #             params,
    #             priority,
    #             cache,
    #             is_active
    #
    #         FROM trading.feature_registry
    #         WHERE is_active = TRUE
    #         ORDER BY priority
    #     """)
    #
    #     with engine.connect() as conn:
    #         result = conn.execute(query)
    #         rows = result.mappings().all()
    #
    #     specs = []
    #     for row in rows:
    #         freqs = row["freqs"]
    #         params = row["params"]
    #
    #         if isinstance(freqs, str):
    #             freqs = json.loads(freqs)
    #
    #         if isinstance(params, str):
    #             params = json.loads(params)
    #
    #         row = dict(row)
    #         row["freqs"] = freqs
    #         row["params"] = params
    #         specs.append(row)
    #
    #     return specs
    #
    #
    #
    #
    #
    # # UTILITIES
    #
    # @staticmethod
    # def _D(value) -> Decimal:
    #     return Decimal(str(value))
    #
    # @staticmethod
    # def _quantize(value: Decimal) -> Decimal:
    #     return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    #
    #
