from typing import Sequence, Optional
from decimal import Decimal

from ib_async import Order, Execution, CommissionReport
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


def D(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


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

    @staticmethod
    def insert_contract(contract) -> None:
        query = text("""
            INSERT INTO contracts (
                con_id, symbol, sec_type, exchange, primary_exchange, currency, local_symbol, trading_class
            )
            VALUES (
                :con_id, :symbol, :sec_type, :exchange, :primary_exchange, :currency, :local_symbol, :trading_class
            )
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "con_id": contract.conId,
                    "symbol": contract.symbol,
                    "sec_type": getattr(contract, 'secType', 'STK'),  # default STK
                    "exchange": getattr(contract, 'exchange', None),
                    "primary_exchange": getattr(contract, 'primaryExchange', None),
                    "currency": contract.currency,
                    "local_symbol": getattr(contract, 'localSymbol', None),
                    "trading_class": getattr(contract, 'tradingClass', None)
                }
            )

    @staticmethod
    def insert_order(order: "Order", account_id: str, portfolio_id: str, con_id: int) -> None:
        query = text("""
                     INSERT INTO orders (perm_id, account_id, portfolio_id, con_id,
                                         action, order_type, tif, quantity, lmt_price,
                                         aux_price, oca_type, order_ref, status,
                                         filled_quantity, remaining_quantity, avg_fill_price,
                                         display_size, reference_price_type, clearing_intent,
                                         cash_qty, ref_futures_con_id, rule80a, openclose,
                                         volatilitytype, created_at, updated_at)
                         
                     VALUES (:perm_id, :account_id, :portfolio_id, :con_id,
                             :action, :order_type, :tif, :quantity, :lmt_price,
                             :aux_price, :oca_type, :order_ref, :status,
                             :filled_quantity, :remaining_quantity, :avg_fill_price,
                             :display_size, :reference_price_type, :clearing_intent,
                             :cash_qty, :ref_futures_con_id, :rule80a, :openclose,
                             :volatilitytype, NOW(), NOW())
                     """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "perm_id": getattr(order, "permId"),
                    "account_id": account_id,
                    "portfolio_id": portfolio_id,
                    "con_id": con_id,
                    "action": getattr(order, "action"),
                    "order_type": getattr(order, "orderType"),
                    "tif": getattr(order, "tif", None),
                    "quantity": getattr(order, "totalQuantity", 0.0),
                    "lmt_price": getattr(order, "lmtPrice", None),
                    "aux_price": getattr(order, "auxPrice", None),
                    "oca_type": getattr(order, "ocaType", None),
                    "order_ref": getattr(order, "orderRef", None),
                    "status": "Submitted",
                    "filled_quantity": getattr(order, "filledQuantity", 0.0),
                    "remaining_quantity": getattr(order, "totalQuantity", 0.0),
                    "avg_fill_price": 0.0,
                    "display_size": getattr(order, "displaySize", None),
                    "reference_price_type": getattr(order, "referencePriceType", 0),
                    "clearing_intent": getattr(order, "clearingIntent", None),
                    "cash_qty": getattr(order, "cashQty", 0.0),
                    "ref_futures_con_id": getattr(order, "refFuturesConId", None),
                    "rule80a": getattr(order, "rule80A", "0"),
                    "openclose": getattr(order, "openClose", ""),
                    "volatilitytype": getattr(order, "volatilityType", 0)
                }
            )

    @staticmethod
    def order_exists(perm_id: int) -> bool:
        query = text("""
                     SELECT 1
                     FROM orders
                     WHERE perm_id = :perm_id
                     LIMIT 1
                     """)

        with engine.connect() as conn:
            result = conn.execute(
                query,
                {"perm_id": perm_id}
            )
            row = result.mappings().first()

        return row is not None

    @staticmethod
    def update_order_status(perm_id: int, status: str, filled_quantity: float, remaining_quantity: float,
                            avg_fill_price: float) -> None:
        query = text("""
                     UPDATE orders
                     SET status             = :status,
                         filled_quantity    = :filled_quantity,
                         remaining_quantity = :remaining_quantity,
                         avg_fill_price     = :avg_fill_price,
                         updated_at         = NOW()
                     WHERE perm_id = :perm_id
                     """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "perm_id": perm_id,
                    "status": status,
                    "filled_quantity": filled_quantity,
                    "remaining_quantity": remaining_quantity,
                    "avg_fill_price": avg_fill_price
                }
            )

    def mark_order_closed(self, trade: "Trade", account_id: str, portfolio_id: str, con_id: int):
        order = trade.order
        order_status = trade.orderStatus
        perm_id = order.permId

        finished_statuses = ("Filled", "Cancelled", "Inactive", "ApiCancelled")
        is_closed = order_status.status in finished_statuses or order_status.remaining == 0

        if not is_closed:
            return

        for fill in trade.fills:
            execution = fill.execution

            self.insert_execution(
                execution=execution,
                account_id=account_id,
                portfolio_id=portfolio_id,
                con_id=con_id,
            )

            if fill.commissionReport:
                self.update_execution_commission(commission=fill.commissionReport)

            self._update_lots(execution, portfolio_id=portfolio_id, con_id=con_id)

            self._insert_position(
                execution=execution,
                portfolio_id=portfolio_id,
                account_id=account_id,
                con_id=con_id,
            )

            self.update_portfolio_ledger(
                execution=execution,
                account_id=account_id,
                portfolio_id=portfolio_id,
                con_id=con_id,
                commission=fill.commissionReport
            )

        self.update_order_status(
            perm_id=perm_id,
            status=order_status.status,
            filled_quantity=order_status.filled,
            remaining_quantity=order_status.remaining,
            avg_fill_price=order_status.avgFillPrice
        )



    @staticmethod
    def insert_execution(execution: "Execution", account_id: str, portfolio_id: str, con_id: int) -> None:

        query = text("""
            INSERT INTO executions (
                exec_id, perm_id, account_id, portfolio_id, con_id,
                side, shares, price, execution_time,
                cum_qty, avg_price, last_liquidity, pending_price_revision
            ) VALUES (
                :exec_id, :perm_id, :account_id, :portfolio_id, :con_id,
                :side, :shares, :price, :execution_time,
                :cum_qty, :avg_price, :last_liquidity, :pending_price_revision
            )
            ON CONFLICT (exec_id) DO NOTHING
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "exec_id": execution.execId,
                    "perm_id": execution.permId,
                    "account_id": account_id,
                    "portfolio_id": portfolio_id,
                    "con_id": con_id,
                    "side": execution.side,
                    "shares": execution.shares,
                    "price": execution.price,
                    "execution_time": execution.time,
                    "cum_qty": execution.cumQty,
                    "avg_price": execution.avgPrice,
                    "last_liquidity": execution.lastLiquidity,
                    "pending_price_revision": execution.pendingPriceRevision,
                }
            )

    @staticmethod
    def update_execution_commission(commission: "CommissionReport") -> None:
        query = text("""
            UPDATE executions
            SET commission = :commission,
                commission_currency = :currency,
                realized_pnl = :realized_pnl,
                created_at = NOW()
            WHERE exec_id = :exec_id
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "exec_id": commission.execId,
                    "commission": commission.commission,
                    "currency": commission.currency,
                    "realized_pnl": commission.realizedPNL
                }
            )

    def _update_lots(self, execution, portfolio_id: str, con_id: int) -> None:
        side = execution.side  # 'BOT' ou 'SLD'

        if side == "BOT":
            self._handle_buy(execution, portfolio_id, con_id)

        elif side == "SLD":
            self._handle_sell(execution, portfolio_id, con_id)

        else:
            raise ValueError(f"Unsupported execution side: {side}")


    def _handle_buy(self, execution, portfolio_id: str, con_id: int) -> None:
        shares = self._D(execution.shares)
        price = self._D(execution.price)

        self._insert_trade_lot(
            portfolio_id=portfolio_id,
            con_id=con_id,
            buy_exec_id=execution.execId,
            quantity=shares,
            price=price,
        )

    @staticmethod
    def _insert_trade_lot(
        portfolio_id: str,
        con_id: int,
        buy_exec_id: str,
        quantity: Decimal,
        price: Decimal,
    ) -> None:
        query = text("""
            INSERT INTO trade_lots (
                portfolio_id,
                con_id,
                buy_exec_id,
                open_quantity,
                closed_quantity,
                price,
                created_at
            )
            VALUES (
                :portfolio_id,
                :con_id,
                :buy_exec_id,
                :open_quantity,
                0,
                :price,
                NOW()
            )
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "portfolio_id": portfolio_id,
                    "con_id": con_id,
                    "buy_exec_id": buy_exec_id,
                    "open_quantity": quantity,
                    "price": price,
                },
            )


    def _handle_sell(self, execution, portfolio_id: str, con_id: int) -> None:
        qty_to_sell = self._D(execution.shares)
        sell_price = self._D(execution.price)

        lots = self._select_open_lots(
            portfolio_id, con_id
        )
        total_available = sum(self._D(lot.open_quantity) for lot in lots)
        if qty_to_sell > total_available:
            raise ValueError(
                "SELL execution exceeds available open lots (short not supported)"
            )


        for lot in lots:
            if qty_to_sell <= 0:
                break

            lot_id = lot.id
            lot_open = self._D(lot.open_quantity)
            lot_price = self._D(lot.price)

            consume_qty = min(lot_open, qty_to_sell)
            realized_pnl = (sell_price - lot_price) * consume_qty

            self._insert_lot_consumption(
                lot_id=lot_id,
                sell_exec_id=execution.execId,
                quantity=consume_qty,
                realized_pnl=realized_pnl,
            )

            self._update_lot_quantities(
                lot_id=lot_id,
                quantity=consume_qty,
            )

            qty_to_sell -= consume_qty


    @staticmethod
    def _select_open_lots(portfolio_id: str, con_id: int):
        query = text("""
            SELECT id, open_quantity, price
            FROM trade_lots
            WHERE portfolio_id = :portfolio_id
              AND con_id = :con_id
              AND open_quantity > 0
            ORDER BY id ASC
        """)

        with engine.begin() as conn:
            return conn.execute(
                query,
                {
                    "portfolio_id": portfolio_id,
                    "con_id": con_id,
                },
            ).fetchall()

    @staticmethod
    def _insert_lot_consumption(
        lot_id: int,
        sell_exec_id: str,
        quantity: Decimal,
        realized_pnl: Decimal,
    ) -> None:
        query = text("""
            INSERT INTO trade_lot_consumption (
                lot_id,
                sell_exec_id,
                quantity,
                realized_pnl,
                created_at
            )
            VALUES (
                :lot_id,
                :sell_exec_id,
                :quantity,
                :realized_pnl,
                NOW()
            )
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "lot_id": lot_id,
                    "sell_exec_id": sell_exec_id,
                    "quantity": quantity,
                    "realized_pnl": realized_pnl,
                },
            )

    @staticmethod
    def _update_lot_quantities(
        lot_id: int,
        quantity: Decimal,
    ) -> None:
        query = text("""
            UPDATE trade_lots
            SET open_quantity = open_quantity - :qty,
                closed_quantity = closed_quantity + :qty,
                updated_at = NOW()
            WHERE id = :lot_id
        """)
        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "qty": quantity,
                    "lot_id": lot_id,
                },
            )

    def _insert_position(
            self,
            execution,
            portfolio_id: str,
            account_id: str,
            con_id: int
    ) -> None:
        filled_qty = self._D(execution.shares)
        fill_price = self._D(execution.price)

        query_select = text("""
                            SELECT quantity, avg_cost
                            FROM positions
                            WHERE account_id = :account_id
                              AND portfolio_id = :portfolio_id
                              AND con_id = :con_id
                            """)

        with engine.begin() as conn:
            result = conn.execute(query_select, {
                "account_id": account_id,
                "portfolio_id": portfolio_id,
                "con_id": con_id
            }).fetchone()


            if result:
                existing_qty, existing_avg = self._D(result.quantity), self._D(result.avg_cost)
            else:
                existing_qty, existing_avg = self._D("0.0"), self._D("0.0")


            if execution.side == "BOT":
                total_qty = existing_qty + filled_qty
                total_cost = existing_qty * existing_avg + filled_qty * fill_price
                avg_cost = total_cost / total_qty if total_qty > 0 else self._D("0.0")

            elif execution.side == "SLD":
                total_qty = existing_qty - filled_qty
                avg_cost = existing_avg

            query_upsert = text("""
                                INSERT INTO positions(account_id, portfolio_id, con_id, quantity, avg_cost)
                                VALUES (:account_id, :portfolio_id, :con_id, :quantity, :avg_cost)
                                ON CONFLICT(account_id, portfolio_id, con_id)
                                    DO UPDATE SET quantity   = :quantity,
                                                  avg_cost   = :avg_cost,
                                                  updated_at = NOW()
                                """)
            conn.execute(query_upsert, {
                "account_id": account_id,
                "portfolio_id": portfolio_id,
                "con_id": con_id,
                "quantity": total_qty,
                "avg_cost": avg_cost
            })


    @staticmethod
    def _get_realized_pnl_from_fifo(exec_id: int) -> Decimal:
        query = text("""
                     SELECT COALESCE(SUM(realized_pnl), 0)
                     FROM trade_lot_consumption
                     WHERE sell_exec_id = :exec_id
                     """)

        with engine.begin() as conn:
            pnl = conn.execute(query, {"exec_id": exec_id}).scalar_one()

        return Decimal(pnl)


    def _build_ledger_entries(
            self,
            execution,
            con_id: int,
            commission: Optional["CommissionReport"] = None,
    ) -> list[dict]:

        side = execution.side
        shares = Decimal(execution.shares)
        price = Decimal(execution.price)
        exec_id = execution.execId
        currency = commission.currency if commission else "USD"

        entries: list[dict] = []

        if side == "BOT":
            entries.append({
                "type": "TRADE_DEBIT",
                "amount": shares * price,
                "con_id": con_id,
                "exec_id": exec_id,
                "currency": currency,
            })

            if commission:
                entries.append({
                    "type": "COMMISSION",
                    "amount": Decimal(commission.commission),
                    "con_id": con_id,
                    "exec_id": exec_id,
                    "currency": commission.currency,
                })

        elif side == "SLD":
            entries.append({
                "type": "TRADE_CREDIT",
                "amount": shares * price,
                "con_id": con_id,
                "exec_id": exec_id,
                "currency": currency,
            })

            pnl = self._get_realized_pnl_from_fifo(exec_id)

            if pnl != Decimal("0"):
                entries.append({
                    "type": "REALIZED_PNL",
                    "amount": pnl,
                    "con_id": con_id,
                    "exec_id": exec_id,
                    "currency": currency,
                })

            if commission:
                entries.append({
                    "type": "COMMISSION",
                    "amount": Decimal(commission.commission),
                    "con_id": con_id,
                    "exec_id": exec_id,
                    "currency": commission.currency,
                })

        else:
            raise ValueError(f"Unsupported execution side: {side}")

        return entries

    def update_portfolio_ledger(
            self,
            execution,
            account_id: str,
            portfolio_id: str,
            con_id: int,
            commission: Optional["CommissionReport"] = None,
    ) -> None:

        entries = self._build_ledger_entries(
            execution,
            con_id,
            commission,
        )

        query = text("""
                     INSERT INTO portfolio_ledger (account_id,
                                                   portfolio_id,
                                                   con_id,
                                                   exec_id,
                                                   type,
                                                   amount,
                                                   currency,
                                                   created_at)
                     VALUES (:account_id,
                             :portfolio_id,
                             :con_id,
                             :exec_id,
                             :type,
                             :amount,
                             :currency,
                             NOW())
                     """)

        with engine.begin() as conn:
            for entry in entries:
                conn.execute(query, {
                    "account_id": account_id,
                    "portfolio_id": portfolio_id,
                    "con_id": entry["con_id"],
                    "exec_id": entry["exec_id"],
                    "type": entry["type"],
                    "amount": entry["amount"],
                    "currency": entry["currency"],
                })

    @staticmethod
    def _D(value) -> Decimal:
        return Decimal(str(value))
