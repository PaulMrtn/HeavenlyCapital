from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, Optional, TYPE_CHECKING
from uuid import UUID

from heavenly_capital.models.order import OrderRequest
from heavenly_capital.models.portfolio import PortfolioSnapshot, Portfolio, Position, PortfolioTarget
from heavenly_capital.data.db_mock import TradingSessionDB


if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts
    from heavenly_capital.core.session_manager import TradingSessionKey


tsDB = TradingSessionDB()


class PortfolioManager:
    def __init__(self) -> None:
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._portfolio: Optional["Portfolio"] = None
        self._portfolio_target: Optional["PortfolioTarget"] = None
        self._market_state = None

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

    def authorize_order(self, order_intent: Dict[str, Any]) -> bool: ...

    def load_portfolio_state(self) -> None:
        if not self._configured:
            raise RuntimeError("PortfolioManager: load_session_state_from_database() called before configure()")

        snapshot: PortfolioSnapshot = self.get_positions_snapshot(
            account_id=self._key.account_id,
            portfolio_id=self._key.portfolio_id)

        self._portfolio = Portfolio.from_snapshot(snapshot)

    def load_portfolio_targets(self):
        today = self._ports.market_calendar.today()
        portfolio_id = self._key.portfolio_id

        if tsDB.check_rebalance_date(portfolio_id, today):
            self._portfolio_target = self.get_portfolio_target(
                portfolio_id=portfolio_id,
                rebalance_date=today
            )

            orders = self.build_rebalance_orders()
            print(orders)



    @property
    def portfolio_state(self) -> Optional[Portfolio]:
        if self._portfolio:
            self._mark_to_market()
        return self._portfolio

    def health_check(self) -> dict[str, Any]:
        return {"is_healthy": True}

    def wire_market_state(self, market_state):
        self._market_state = market_state

    @staticmethod
    def get_positions_snapshot(
            account_id: str,
            portfolio_id: str,
    ) -> PortfolioSnapshot:
        rows = tsDB.fetch_positions(portfolio_id=portfolio_id)

        positions: Dict[int, Position] = {}

        if rows:
            as_of = max(r["updated_at"] for r in rows)

            for r in rows:
                positions[r["con_id"]] = Position(
                    symbol=r["symbol"],
                    quantity=Decimal(r["quantity"]),
                    avg_price=Decimal(r["avg_cost"]),
                )
        else:
            as_of = None

        cash = Decimal("100000")

        return PortfolioSnapshot(
            account_id=account_id,
            as_of=as_of,
            base_currency="USD",
            cash=cash,
            positions=positions,
        )

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

        orders: list[OrderRequest] = []

        total_value = self._portfolio.total_value
        all_instruments = set(self._portfolio.positions.keys()) | set(self._portfolio_target.weights.keys())

        for con_id in all_instruments:
            target_weight = Decimal(str(self._portfolio_target.weights.get(con_id, 0)))

            position = self._portfolio.positions.get(con_id)
            current_qty = position.quantity if position else Decimal("0")
            market_price = position.market_price if position and position.market_price is not None else None
            if market_price is None or market_price == 0:
                continue

            target_value = target_weight * total_value
            target_qty = (target_value / market_price).quantize(Decimal("1"), rounding=ROUND_DOWN)

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
        if not self._portfolio or not self._market_state:
            return

        for con_id, position in self._portfolio.positions.items():
            market_data = self._market_state.get(con_id).as_dict()
            if not market_data:
                continue

            position.mark_to_market(market_data)




