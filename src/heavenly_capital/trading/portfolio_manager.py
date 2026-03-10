from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, TYPE_CHECKING, Callable
from uuid import UUID

from heavenly_capital.core.runtime_config import BaseModule, ModuleType
from heavenly_capital.models.market_data import TickerManager
from heavenly_capital.models.order import OrderRequest, OrderTracker
from heavenly_capital.models.portfolio import PortfolioSnapshot, Portfolio, Position, PortfolioTarget
from heavenly_capital.data.db_mock import TradingSessionDB


if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey


tsDB = TradingSessionDB()


class PortfolioManager(BaseModule):
    def __init__(self) -> None:
        super().__init__()
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._portfolio: Optional["Portfolio"] = None
        self._portfolio_target: Optional["PortfolioTarget"] = None
        self._tickers = None

        self.live_orders: list[OrderTracker] = []

        self._configured = False
        self._started = False

    def configure(self, *, session_id: UUID, key: "TradingSessionKey", ports: "SystemPorts") -> None:
        self._key = key
        self._session_id = session_id
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("PortfolioManager: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        self._started = False

    def dispatch(self, target: ModuleType, action: str, data: Any) -> None:
        payload = {
            "action": action,
            "data": data
        }
        self.send(target, payload)

    def receive(self, payload: dict[str, Any], source: ModuleType) -> None:
        action = payload.get("action")
        data = payload.get("data")

        dispatch: dict[tuple[ModuleType, str], Callable] = {
            (ModuleType.ORDERS, "order_tracking"): self._handle_order_tracking,
        }

        handler = dispatch.get((source, action))
        if handler:
            handler(data)


    def load_portfolio_state(self) -> None:
        if not self._configured:
            raise RuntimeError("PortfolioManager: load_session_state_from_database() called before configure()")

        snapshot = self.get_portfolio_snapshot(
            account_id=self._key.account_id,
            portfolio_id=self._key.portfolio_id)

        self._portfolio = Portfolio.from_snapshot(snapshot)


    def load_portfolio_orders(self):
        today = self._ports.market_calendar.today()
        portfolio_id = self._key.portfolio_id

        if tsDB.check_rebalance_date(portfolio_id, today):
            self._portfolio_target = self.get_portfolio_target(
                portfolio_id=portfolio_id,
                rebalance_date=today
            )

            orders = self.build_rebalance_orders()

            self.dispatch(ModuleType.ORDERS, "order_request", orders)


    @property
    def portfolio_state(self) -> Optional[Portfolio]:
        if self._portfolio:
            self._mark_to_market()
        return self._portfolio

    def health_check(self) -> dict[str, Any]:
        return {"is_healthy": True}

    def wire_ticker_manager(self, tickers_manager: "TickerManager"):
        self._tickers = tickers_manager
        self._tickers.subscribe(self.refresh_portfolio)


    @staticmethod
    def _build_portfolio_snapshot(
            account_id: str,
            portfolio_id: str,
            positions: Dict[int, Position],
    ) -> PortfolioSnapshot:

        balance = tsDB.get_portfolio_balance(portfolio_id, account_id)

        return PortfolioSnapshot(
            portfolio_id=portfolio_id,
            account_id=account_id,
            base_currency="USD",
            balance=balance,
            positions=positions,
        )

    def get_portfolio_snapshot(
            self,
            account_id: str,
            portfolio_id: str,
    ) -> PortfolioSnapshot:
        rows = tsDB.fetch_positions(portfolio_id=portfolio_id)

        positions: Dict[int, Position] = {}
        for r in rows:
            positions[r["con_id"]] = Position(
                symbol=r["symbol"],
                quantity=Decimal(r["quantity"]),
                avg_price=Decimal(r["avg_cost"]),
            )

        portfolio = self._build_portfolio_snapshot(
            account_id=account_id,
            portfolio_id=portfolio_id,
            positions=positions,
        )

        return portfolio


    @staticmethod
    def get_portfolio_target(portfolio_id: str, rebalance_date: str) -> "PortfolioTarget":

        rows = tsDB.fetch_portfolio_targets(
            portfolio_id=portfolio_id,
            rebalance_date=rebalance_date)

        if not rows:
            raise ValueError(f"No target found for portfolio {portfolio_id} on {rebalance_date}")

        weights = {row["con_id"]: row["target_weight"] for row in rows}
        rebalance_date = rows[0]["rebalance_date"]

        return PortfolioTarget(weights=weights, rebalance_date=rebalance_date)


    def build_rebalance_orders(self) -> list["OrderRequest"]:
        if not self._portfolio or not self._portfolio_target:
            return []

        orders: list["OrderRequest"] = []

        total_value = self._portfolio.total_value
        print(f"Total portfolio value: {total_value}")

        all_instruments = set(self._portfolio.positions.keys()) | set(self._portfolio_target.weights.keys())

        for con_id in all_instruments:
            market_data = self._tickers.get_ticker(con_id).as_dict()
            #TODO:WARNING turn bid to last
            last = market_data.get("bid")
            market_price = Decimal(str(last))
            if market_price <= 0:
                continue

            position = self._portfolio.positions.get(con_id)
            current_qty = position.quantity if position else Decimal("0")

            target_weight = Decimal(str(
                self._portfolio_target.weights.get(con_id, 0)
            ))

            target_value = target_weight * total_value
            target_qty = (target_value / market_price).quantize(Decimal("1"), rounding=ROUND_DOWN)

            delta_qty = target_qty - current_qty
            if delta_qty == 0:
                continue

            print(f"con_id: {con_id} | current_qty: {current_qty} | target_qty: {target_qty} | delta_qty: {delta_qty}")

            order_side = "BUY" if delta_qty > 0 else "SELL"

            # TODO:MEDIUM : add order strategies (MKT, LMT, pegged, ...)
            orders.append(
                OrderRequest.create(
                account_id=self._portfolio.account_id,
                portfolio_id=self._key.portfolio_id,
                con_id=con_id,
                side=order_side,
                quantity=float(abs(delta_qty)),
                order_type="MKT",
            ))

        return orders


    def _mark_to_market(self) -> None:
        if not self._portfolio or not self._tickers:
            return

        for con_id, position in self._portfolio.positions.items():
            market_data = self._tickers.get_ticker(con_id).as_dict()
            if not market_data:
                continue

            position.mark_to_market(market_data)


    def refresh_portfolio(self) -> None:
        if not self._portfolio:
            return

        self._mark_to_market()
        self._portfolio.refresh_balance()
        self._portfolio.update_database()


    def authorize_order(self, con_id: int) -> None:
        auth_payload = {
            "con_id": con_id,
            "authorized":True
        }

        self.dispatch(ModuleType.ORDERS, "authorize_order", auth_payload)


    def _handle_order_tracking(self, order: OrderTracker):
        self.live_orders.append(order)

        order.state.on_filled = lambda state=None, tracker=order: self._apply_fill_to_portfolio(tracker)


    def _apply_fill_to_portfolio(self, order: OrderTracker) -> None:
        if not self._portfolio:
            return

        con_id = order.request.con_id
        side = order.request.side
        symbol = order.contract.symbol
        fill_qty = Decimal(str(order.state.filled_quantity))
        fill_price = Decimal(str(order.state.avg_fill_price))
        commission = Decimal(str(order.state.commission))

        position = self._portfolio.positions.get(con_id)


        if side == "BUY":
            if position:
                total_cost = position.avg_price * position.quantity + fill_price * fill_qty
                new_qty = position.quantity + fill_qty
                position.avg_price = (total_cost / new_qty).quantize(Decimal("0.0001"))
                position.quantity = new_qty
            else:
                self._portfolio.positions[con_id] = Position(
                    symbol=symbol,
                    quantity=fill_qty,
                    avg_price=fill_price
                )

            self._portfolio.balance.cash -= fill_qty * fill_price
            self._portfolio.balance.total_commission += commission

        elif side == "SELL":
            if not position:
                return
            position.quantity -= fill_qty
            self._portfolio.balance.cash += fill_qty * fill_price
            self._portfolio.balance.total_commission += commission

            if position.quantity == 0:
                del self._portfolio.positions[con_id]
            elif position.quantity < 0:
                raise ValueError(
                    f"Position quantity negative for {symbol} (con_id={con_id}). "
                    f"Tried to sell {fill_qty}, but only {position.quantity + fill_qty} available."
                )

        if order in self.live_orders:
            self.live_orders.remove(order)









    def authorize_all_current_orders(self) -> None:
        #TODO:WARNING Temporary Function
        if not self._portfolio or not self._portfolio_target:
            return

        all_instruments = set(self._portfolio.positions.keys()) | set(self._portfolio_target.weights.keys())

        for con_id in all_instruments:
            self.authorize_order(con_id)






