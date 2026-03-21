from __future__ import annotations

import time
from threading import Lock
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, TYPE_CHECKING, Callable
from uuid import UUID

from heavenly_capital.core.runtime_config import BaseModule, ModuleType
from heavenly_capital.data.bus import EventBus
from heavenly_capital.models.market_data import TickerManager
from heavenly_capital.models.order import OrderRequest, OrderTracker
from heavenly_capital.models.portfolio import PortfolioSnapshot, Portfolio, Position, PortfolioTarget, PortfolioBalance

if TYPE_CHECKING:
    from heavenly_capital.core.kernel import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey
    from heavenly_capital.strategy.artifacts import ModelOutput, ModelSignal


UPDATE_INTERVAL = 5


class PortfolioManager(BaseModule):

    def __init__(self) -> None:
        super().__init__()
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._portfolio: Optional["Portfolio"] = None
        self._portfolio_lock = Lock()
        self._portfolio_target: Optional["PortfolioTarget"] = None
        self._tickers = None
        self.live_orders: list[OrderTracker] = []

        self._in_bus: Optional["EventBus"] = None
        self._in_token: Optional[int] = None

        self._last_db_update_interval = -1

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

        if self._ports.db_service.reader.check_rebalance_date(portfolio_id, today):
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

    def wire_forecast_manager(self, bus: "EventBus"):
        self._in_bus = bus

        #TODO:WARNING : Rewrite wire logic and use start, stop, configure with session manager
        self.subscribe_to_forecast_manager()

    def subscribe_to_forecast_manager(self) -> None:
        if self._in_token is None and self._in_bus is None:
            raise RuntimeError("PortfolioManager: input bus not set (call wire_forecast_manager() first)")

        self._in_token =  self._in_bus.subscribe(
            entity_id=self._key.portfolio_id,
            callback=self._handle_signal
        )

    def _handle_signal(self, portfolio_id, signal: "ModelSignal"):
        if signal.output.decision:
            self.authorize_order(signal)


    @staticmethod
    def build_portfolio_snapshot(
            account_id: str,
            portfolio_id: str,
            positions: Dict[int, Position],
            balance: dict
    ) -> PortfolioSnapshot:

        _balance = PortfolioBalance(
            cash=balance["total_cash_balance"],
            stock_market_value=balance["stock_market_value"],
            unrealized_pnl=balance["unrealized_pnl"]
        )

        return PortfolioSnapshot(
            portfolio_id=portfolio_id,
            account_id=account_id,
            base_currency="USD",
            balance=_balance,
            positions=positions,
        )

    def get_portfolio_snapshot(
            self,
            account_id: str,
            portfolio_id: str,
    ) -> PortfolioSnapshot:

        rows = self._ports.db_service.reader.fetch_positions(portfolio_id=portfolio_id)

        positions: Dict[int, Position] = {}
        for r in rows:
            positions[r["con_id"]] = Position(
                symbol=r["symbol"],
                quantity=Decimal(r["quantity"]),
                avg_price=Decimal(r["avg_cost"]),
            )

        balance = self._ports.db_service.reader.get_portfolio_balance(portfolio_id, account_id)

        return self.build_portfolio_snapshot(
            account_id=account_id,
            portfolio_id=portfolio_id,
            positions=positions,
            balance=balance
        )

    def get_portfolio_target(self, portfolio_id: str, rebalance_date: str) -> "PortfolioTarget":

        rows = self._ports.db_service.reader.fetch_portfolio_targets(
            portfolio_id=portfolio_id,
            rebalance_date=rebalance_date)

        if not rows:
            return PortfolioTarget(weights={}, rebalance_date=rebalance_date)

        weights = {row["con_id"]: row["target_weight"] for row in rows}
        rebalance_date = rows[0]["rebalance_date"]

        return PortfolioTarget(weights=weights, rebalance_date=rebalance_date)


    def build_rebalance_orders(self) -> list["OrderRequest"]:
        if not self._portfolio or not self._portfolio_target:
            return []

        orders: list["OrderRequest"] = []

        total_value = self._portfolio.total_value

        all_instruments = (set(self._portfolio.positions.keys())
                           | set(self._portfolio_target.weights.keys()))

        for con_id in all_instruments:
            market_data = self._tickers.get_ticker(con_id).as_dict()
            last = market_data.get("bid")   #TODO:WARNING turn bid to last
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
            # TODO:HIGH Add mechanism to converge portfolio cash to 0

            delta_qty = target_qty - current_qty
            if delta_qty == 0:
                continue

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

    def update_database(self, current_time: float) -> None:
        current_interval = int(current_time) // UPDATE_INTERVAL

        if current_interval != self._last_db_update_interval:
            self._last_db_update_interval = current_interval
            self._ports.db_service.writer.update_portfolio_in_db(self._portfolio)


    def refresh_portfolio(self) -> None:
        if not self._portfolio:
            return

        with self._portfolio_lock:
            self._mark_to_market()
            self._portfolio.refresh_balance()

        self.update_database(time.time())

    def authorize_order(self, signal: ModelSignal) -> None:
        if not signal.output.decision:
            return

        self.dispatch(ModuleType.ORDERS, "authorize_order", signal)

    def _handle_order_tracking(self, order: OrderTracker):
        self.live_orders.append(order)

        order.state.on_fully_filled = lambda state=None, tracker=order: self._update_portfolio_after_fully_filled(tracker)

    def _update_portfolio_after_fully_filled(self, order: OrderTracker) -> None:
        if not self._portfolio:
            return

        with self._portfolio_lock:
            data = self._extract_order_data(order)

            if data["side"] == "BUY":
                self._process_buy(**data)
            elif data["side"] == "SELL":
                self._process_sell(**data)

            if order in self.live_orders:
                self.live_orders.remove(order)

            self._update_portfolio_balance(order)

    def _extract_order_data(self, order: OrderTracker) -> dict:
        return {
            "order": order,
            "con_id": order.request.con_id,
            "side": order.request.side,
            "symbol": order.contract.symbol,
            "fill_qty": Decimal(str(order.state.filled_quantity)),
            "fill_price": Decimal(str(order.state.avg_fill_price)),
            "commission": Decimal(str(order.state.commission)),
            "position": self._portfolio.positions.get(order.request.con_id)
        }

    def _process_buy(self, order, con_id, symbol, fill_qty, fill_price, commission, position, **_):
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

    def _process_sell(self, order, con_id, symbol, fill_qty, fill_price, commission, position, **_):
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


    def _update_portfolio_balance(self, order: OrderTracker) -> None:
        self._ports.db_service.writer.update_portfolio_balances(
            account_id=order.request.account_id,
            portfolio_id=order.request.portfolio_id
        )

    def authorize_all_current_orders(self) -> None:
        # WARNING: Temporary testing helper
        if not self._portfolio or not self._portfolio_target:
            return

        all_instruments = (
                set(self._portfolio.positions.keys())
                | set(self._portfolio_target.weights.keys())
        )

        for conid in all_instruments:
            signal = ModelSignal(
                conid=conid,
                model_id="mock",
                model_type="mock",
                output=ModelOutput(decision=True)
            )

            self.authorize_order(signal)




