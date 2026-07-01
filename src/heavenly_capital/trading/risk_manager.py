from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING, Callable, Hashable
from uuid import UUID

from heavenly_capital.data.bus import EventBus
from heavenly_capital.models.market_data import ReadOnlyTicker
from heavenly_capital.models.order import OrderRequest
from heavenly_capital.models.risk import StopLossStore, MonitoredPosition, TriggerReason
from heavenly_capital.models.runtime import BaseModule, ModuleType
from heavenly_capital.strategy.artifacts import ModelKind

if TYPE_CHECKING:
    from heavenly_capital.core.kernel import SystemPorts
    from heavenly_capital.trading.session_manager import TradingSessionKey
    from heavenly_capital.strategy.artifacts import ModelSignal


class RiskManager(BaseModule):
    def __init__(self) -> None:
        super().__init__()
        self._session_id: Optional[UUID] = None
        self._ports: Optional["SystemPorts"] = None
        self._key: Optional["TradingSessionKey"] = None

        self._in_bus: Optional["EventBus"] = None
        self._in_token: Optional[int] = None

        self._store : Optional["StopLossStore"] = None
        self._tickers = None

        self._configured = False
        self._started = False

    def configure(self, session_id: UUID, key: "TradingSessionKey", ports: "SystemPorts") -> None:
        self._key = key
        self._session_id = session_id
        self._ports = ports
        self._configured = True

    def start(self) -> None:
        if not self._configured:
            raise RuntimeError("RiskMonitor: start() called before configure()")
        self._started = True

    def stop(self) -> None:
        # TODO:WARNING : add unsubscribe logic here (self._in_bus.unsubscribe(self._in_token))
        self._started = False


    def health_check(self) -> dict[str, Any]:
        return {
            "is_healthy": True,
        }


    def load_thresholds(self) -> None:
        rows = self._ports.db_service.reader.fetch_portfolio_thresholds(
            portfolio_id=self._key.portfolio_id
        )
        self._store = StopLossStore.from_rows(rows)

    def dispatch(self, target: ModuleType, action: str, data: Any) -> None:
        payload = {
            "action": action,
            "data": data
        }
        self.send(target, payload)

    def receive(self, payload: dict, source: ModuleType) -> None:
        action: str = payload.get("action", "")
        data: dict = payload.get("data", {})

        dispatch: dict[tuple[ModuleType, str], Callable] = {
            (ModuleType.PORTFOLIO, "position_updated"): self._on_position_updated,
            (ModuleType.PORTFOLIO, "position_closed"): self._on_position_closed,
        }

        handler = dispatch.get((source, action))
        if handler:
            handler(data)


    def _on_position_updated(self, data: dict) -> None:
        if self._store is None:
            return
        self._store.on_fill_updated(
            con_id=data["con_id"],
            avg_cost=data["avg_cost"],
            quantity=data["quantity"]
        )

    def _on_position_closed(self, data: dict) -> None:
        if self._store is None:
            return

        self._store.on_closed(con_id=data["con_id"])


    def wire_ticker_manager(self, tickers_manager):
        self._tickers = tickers_manager
        self._tickers.subscribe(self._on_price_update)

    def wire_forecast_manager(self, bus: "EventBus") -> None:
        self._in_bus = bus
        self.subscribe_to_forecast_manager()

    def subscribe_to_forecast_manager(self) -> None:
        if self._in_token is None and self._in_bus is None:
            raise RuntimeError("RiskManager: input bus not set (call wire_forecast_manager() first)")

        self._in_token =  self._in_bus.subscribe(
            entity_id=self._key.portfolio_id,
            callback=self._handle_signal
        )

    def _handle_signal(self, portfolio_id: Hashable, signal: "ModelSignal") -> None:
        if signal.model_type != ModelKind.STOP_LOSS:
            return

        clock = self._ports.market_clock
        if not clock.is_market_open:
            return

        if signal.output.decision:
            self._on_stop_loss_signal(signal.conid)


    def _on_stop_loss_signal(self, con_id: int) -> None:
        if self._store is None:
            return
        if not self._store.is_monitoring(con_id):
            return

        self._ports.log_service.info(
            "Risk ML signal received",
            extra={
                "domain": "RISK",
                "event": "ml_signal",
                "portfolio_id": self._key.portfolio_id,
                "account_id": self._key.account_id,
                "con_id": con_id,
            }
        )

        self._trigger_execution(con_id, reason=TriggerReason.ML_SIGNAL)


    def authorize_order(self, con_id: int) -> None:
        # TODO:LOW — inutilisé, internaliser dans RiskManager._authorize_execution
        auth_payload = {
            "con_id": con_id,
            "authorized":True
        }

        self.dispatch(ModuleType.ORDERS, "authorize_order", auth_payload)

    def _on_price_update(self) -> None:
        if not self._store or not self._tickers:
            return

        for pos in self._store.all_monitoring():
            ticker = self._tickers.get_ticker(pos.con_id)
            if not ticker:
                continue
            self._evaluate_position(pos, ticker)


    def _evaluate_position(self, pos: "MonitoredPosition", ticker: "ReadOnlyTicker") -> None:
        last_price = ticker.last
        clock = self._ports.market_clock

        if clock.is_pre_market or clock.is_post_market:
            if last_price <= pos.threshold_abs:
                self._trigger_execution(pos.con_id, reason=TriggerReason.HIT_THRESHOLD)
                return


            # Buffer S-B post/pre market uniquement
            # TODO:LOW - Finish Buffer S-B post/pre marke Rule case
            # if pos.threshold_abs - TRESHOLD_BUFFER <= prix < pos.threshold_abs:
            #     self._trigger_execution(pos.con_id, reason=TriggerReason.BUFFER_BREACH)
            #     return


        # Force Close 15h55 (step 385 = 15h55)
        # TODO:LOW - Finish Force Close Rule case
        # if clock.is_market_open and clock.step_state >= 385:
        #     distance = (prix - pos.threshold_abs) / prix
        #     if distance <= FORCE_CLOSE_THRESHOLD:
        #         self._trigger_execution(pos.con_id, reason=TriggerReason.FORCE_CLOSE)
        #         return


    def _authorize_execution(self, con_id: int) -> bool:
        # V1 : toujours autorisé
        # TODO:LOW — future : vérifier spread/bid_size/ask_size avant exécution
        return True


    def _trigger_execution(self, con_id: int, reason: str) -> None:
        if not self._store.is_monitoring(con_id):
            return

        pos = self._store.get(con_id)
        if pos is None:
            return

        if not self._authorize_execution(con_id):
            return

        self._store.on_order_sent(con_id)

        order = OrderRequest.create(
            account_id=self._key.account_id,
            portfolio_id=self._key.portfolio_id,
            con_id=con_id,
            side="SELL",
            quantity=pos.quantity,
            order_type="MKT",
        )

        self._ports.log_service.info(
            "Risk trigger executed",
            extra={
                "domain": "RISK",
                "event": "trigger_executed",
                "portfolio_id": self._key.portfolio_id,
                "account_id": self._key.account_id,
                "con_id": con_id,
                "reason": reason,
                "threshold_abs": round(pos.threshold_abs, 4),
            }
        )

        self.dispatch(ModuleType.ORDERS, "order_request", order)



# TODO:MEDIUM — mesurer la latence de _on_price_update sur plusieurs portfolios en parallèle.
# Vérifier que le callback à 0.5s ne s'accumule pas si le traitement dépasse l'intervalle,
# et que l'exécution reste isolée par portfolio (pas de blocage cross-portfolio).