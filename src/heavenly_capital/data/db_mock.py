from typing import Sequence, Optional
from decimal import Decimal

from ib_async import Order, Execution, CommissionReport
from sqlalchemy import text, RowMapping
from sqlalchemy import create_engine


from decimal import Decimal, ROUND_HALF_UP



class UnitOfWork:
    def __enter__(self):
        self.conn = engine.connect()        # Connexion normale
        self.trans = self.conn.begin()      # Transaction explicite
        return self.conn                    # On retourne la connexion pour l'utiliser

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.trans.rollback()
        else:
            self.trans.commit()
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
            ON CONFLICT (con_id) DO NOTHING;
        """)

        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "con_id": contract.conId,
                    "symbol": contract.symbol,
                    "sec_type": contract.secType,
                    "exchange": contract.exchange,
                    "primary_exchange": contract.primaryExchange,
                    "currency": contract.currency,
                    "local_symbol": contract.localSymbol,
                    "trading_class": contract.tradingClass
                }
            )


    @staticmethod
    def insert_order(order: "Order", account_id: str, portfolio_id: str, con_id: int) -> None:
        query = text("""
                     INSERT INTO orders (perm_id, account_id, portfolio_id, con_id, action, order_ref, order_type, tif,
                                         quantity,
                                         lmt_price, aux_price, status, filled_quantity, remaining_quantity,
                                         avg_fill_price,
                                         reference_price_type, oca_group, oca_type, created_at, updated_at)
                     VALUES (:perm_id, :account_id, :portfolio_id, :con_id, :action, :order_ref, :order_type, :tif,
                             :quantity,
                             :lmt_price, :aux_price, :status, :filled_quantity, :remaining_quantity, :avg_fill_price,
                             :reference_price_type, :oca_group, :oca_type, NOW(), NOW())
                     ON CONFLICT (perm_id) DO NOTHING
                     """)

        print()


        with engine.begin() as conn:
            conn.execute(
                query,
                {
                    "perm_id": order.permId,
                    "account_id": account_id,
                    "portfolio_id": portfolio_id,
                    "con_id": con_id,
                    "action": order.action,
                    "order_ref": order.orderRef,
                    "order_type": order.orderType,
                    "tif": order.tif,
                    "quantity": order.totalQuantity,
                    "lmt_price": order.lmtPrice,
                    "aux_price": order.auxPrice if order.auxPrice <= 1e11 else None,
                    "status": "PendingSubmit",
                    "filled_quantity": 0.0,
                    "remaining_quantity": order.totalQuantity,
                    "avg_fill_price": 0.0,
                    "reference_price_type": 0 if order.referencePriceType == 2147483647 else order.referencePriceType,
                    "oca_group": order.ocaGroup,
                    "oca_type": order.ocaType
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


    @staticmethod
    def insert_execution(conn : "Connection", execution: "Execution", account_id: str, portfolio_id: str, con_id: int) -> None:
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

    def _update_lots(self, conn : "Connection", execution, portfolio_id: str, con_id: int) -> None:
        side = execution.side  # 'BOT' ou 'SLD'

        if side == "BOT":
            self._handle_buy(conn, execution, portfolio_id, con_id)

        elif side == "SLD":
            self._handle_sell(conn, execution, portfolio_id, con_id)

        else:
            raise ValueError(f"Unsupported execution side: {side}")


    def _handle_buy(self, conn : "Connection", execution, portfolio_id: str, con_id: int) -> None:
        shares = self._D(execution.shares)
        price = self._D(execution.price)

        self._insert_trade_lot(
            conn=conn,
            portfolio_id=portfolio_id,
            con_id=con_id,
            buy_exec_id=execution.execId,
            quantity=shares,
            price=price,
        )

    @staticmethod
    def _insert_trade_lot(
        conn: "Connection",
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
            VALUES (:portfolio_id,
                    :con_id,
                    :buy_exec_id,
                    :open_quantity,
                    0,
                    :price,
                    NOW()
            )
            ON CONFLICT (portfolio_id, buy_exec_id) DO NOTHING

            
        """)

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


    def _handle_sell(self, conn : "Connection", execution, portfolio_id: str, con_id: int) -> None:
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
                conn=conn,
                lot_id=lot_id,
                sell_exec_id=execution.execId,
                quantity=consume_qty,
                realized_pnl=realized_pnl,
            )

            self._update_lot_quantities(
                conn=conn,
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
        conn: "Connection",
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
        conn: "Connection",
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

        conn.execute(
            query,
            {
                "qty": quantity,
                "lot_id": lot_id,
            },
        )

    @staticmethod
    def _insert_position(
            conn: "Connection",
            portfolio_id: str,
            account_id: str,
            con_id: int
    ) -> None:

        query_exec = text("""
                          SELECT side, shares, price
                          FROM executions
                          WHERE account_id = :account_id
                            AND portfolio_id = :portfolio_id
                            AND con_id = :con_id
                          ORDER BY execution_time, exec_id
                          """)

        executions = conn.execute(query_exec, {
            "account_id": account_id,
            "portfolio_id": portfolio_id,
            "con_id": con_id
        }).fetchall()

        total_qty = Decimal("0.0")
        total_cost = Decimal("0.0")

        for exec_row in executions:
            side = exec_row.side
            shares = Decimal(exec_row.shares)
            price = Decimal(exec_row.price)

            if side == "BOT":
                total_qty += shares
                total_cost += shares * price

            elif side == "SLD":
                total_qty -= shares

                if total_qty < 0:
                    raise ValueError("SELL execution exceeds available quantity")

        avg_cost = total_cost / total_qty if total_qty > 0 else Decimal("0.0")

        if total_qty > 0:
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
        else:
            query_delete = text("""
                                DELETE
                                FROM positions
                                WHERE account_id = :account_id
                                  AND portfolio_id = :portfolio_id
                                  AND con_id = :con_id
                                """)
            conn.execute(query_delete, {
                "account_id": account_id,
                "portfolio_id": portfolio_id,
                "con_id": con_id
            })


    @staticmethod
    def _get_realized_pnl_from_fifo(conn: "Connection", exec_id: int) -> Decimal:
        query = text("""
                     SELECT COALESCE(SUM(realized_pnl), 0)
                     FROM trade_lot_consumption
                     WHERE sell_exec_id = :exec_id
                     """)


        pnl = conn.execute(query, {"exec_id": exec_id}).scalar_one()

        return Decimal(pnl)


    def _build_ledger_entries(
            self,
            conn: "Connection",
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
                "amount": self._quantize(shares * price),
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
                "amount": self._quantize(shares * price),
                "con_id": con_id,
                "exec_id": exec_id,
                "currency": currency,
            })

            pnl = self._get_realized_pnl_from_fifo(conn, exec_id)

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
            conn: "Connection",
            execution,
            account_id: str,
            portfolio_id: str,
            con_id: int,
            commission: Optional["CommissionReport"] = None,
    ) -> None:

        entries = self._build_ledger_entries(
            conn,
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
                     ON CONFLICT (exec_id, type) DO NOTHING
                     """)

        for entry in entries:
            if entry["type"] == "COMMISSION" and entry["amount"] == 0:
                continue
            currency = entry.get("currency") or "USD"

            conn.execute(query, {
                "account_id": account_id,
                "portfolio_id": portfolio_id,
                "con_id": entry["con_id"],
                "exec_id": entry["exec_id"],
                "type": entry["type"],
                "amount": entry["amount"],
                "currency": currency,
            })


    def update_order_in_db(
            self,
            trade: "Trade",
            perm_id: int,
            portfolio_id: str,
            account_id: str
    ):
        order_status = trade.orderStatus
        order = trade.order
        contract = trade.contract

        if not self.order_exists(perm_id):
            self.insert_order(
                order=order,
                portfolio_id=portfolio_id,
                account_id=account_id,
                con_id=contract.conId
            )

        self.update_order_status(
            perm_id=perm_id,
            status=order_status.status,
            filled_quantity=order_status.filled,
            remaining_quantity=order_status.remaining,
            avg_fill_price=order_status.avgFillPrice
        )

        if order_status.status in ("Cancelled", "Inactive", "ApiCancelled"):
            self.update_order_status(
                perm_id=perm_id,
                status=order_status.status,
                filled_quantity=order_status.filled,
                remaining_quantity=order_status.remaining,
                avg_fill_price=order_status.avgFillPrice
            )

            # retry_order(order_id) add cancelOrder()

    def update_fill_in_db(
            self,
            *,
            execution,
            fill,
            account_id: str,
            portfolio_id: str,
            con_id: int
    ):
        with UnitOfWork() as conn:
            self.insert_execution(
                conn=conn,
                execution=execution,
                account_id=account_id,
                portfolio_id=portfolio_id,
                con_id=con_id
            )

            self._update_lots(
                conn=conn,
                execution=execution,
                portfolio_id=portfolio_id,
                con_id=con_id
            )

            self._insert_position(
                conn=conn,
                portfolio_id=portfolio_id,
                account_id=account_id,
                con_id=con_id
            )

            self.update_portfolio_ledger(
                conn=conn,
                execution=execution,
                commission=getattr(fill, "commissionReport", None),
                account_id=account_id,
                portfolio_id=portfolio_id,
                con_id=con_id
            )


    def update_commission_in_db(
        self,
        *,
        execution,
        commission,
        account_id: str,
        portfolio_id: str,
        con_id: int
    ):

        with UnitOfWork() as conn:
            self.update_portfolio_ledger(
                conn=conn,
                execution=execution,
                commission=commission,
                account_id=account_id,
                portfolio_id=portfolio_id,
                con_id=con_id
            )


    @staticmethod
    def _D(value) -> Decimal:
        return Decimal(str(value))

    @staticmethod
    def _quantize(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)