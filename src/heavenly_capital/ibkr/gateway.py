from __future__ import annotations

from datetime import timezone, datetime
from typing import Optional, Any, Callable, TYPE_CHECKING

from ib_async import Contract, Ticker, Trade, Order, MarketOrder, LimitOrder

from heavenly_capital.core.runtime_config import IBKRConfig, AsyncRuntimeModule
from heavenly_capital.ibkr.client import ClientManager
from heavenly_capital.models.order import OrderTracker, OrderRequest
from heavenly_capital.models.tickers import UniverseSnapshot

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts



CLIENTS_CONFIG = [
    {
        "session_name": "SESSION_1", # client_id
        "host": "127.0.0.1",
        "port": 4002,
        "enable": True,
        "account_id" : "DUO800430",
        "account_type": "PAPER",         # LIVE ou PAPER
        "permission_level": "MASTER"    # MASTER ou STANDARD
    },
    {
        "session_name": "SESSION_2",
        "host": "127.0.0.1",
        "port": 4003,
        "enable": True,
        "account_id" : "DUM832619",
        "account_type": "PAPER",
        "permission_level": "STANDARD"
    },

]

UTC_ZONE = timezone.utc


class IBKRGateway(AsyncRuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional["IBKRConfig"] = None
        self._ports: Optional["SystemPorts"] = None

        self.manager: Optional["ClientManager"] = None
        self._contracts: Optional[dict[str, "Contract"]] = None

        self._order_registry: dict[str, "OrderTracker"] = {}


    def configure(self, *, config: "IBKRConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self.manager = ClientManager(CLIENTS_CONFIG) # config.sessions
        self._configured = True

    async def start(self) -> None:
        if not self._configured:
            raise RuntimeError("IBKRGateway: start() called before configure()")
        await self.manager.start()

        for client in self.manager.all:
            client.events.order_status = self._on_order_status
            client.events.exec_details = self._on_fill
            client.events.commission_report = self._on_commission

        self._started = True

    def stop(self) -> None:
        self._started = False

    @property
    def is_configured(self) -> bool:
        return self._configured

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def config(self) -> IBKRConfig:
        if self._config is None:
            raise RuntimeError("IBKRGateway: config not set (configure() not called)")
        return self._config

    @property
    def ports(self) -> "SystemPorts":
        if self._ports is None:
            raise RuntimeError("IBKRGateway: ports not set (configure() not called)")
        return self._ports

    def health_check(self) -> dict[str, Any]:
        return {"is_healthy": True}


    # --- order / trade API ----------

# Cehck si dans lobjet OGR cette fonction qui compatabiel (nouvelle singature)

    def order_sink(self, tracker: "OrderTracker") -> None:
        if not self._configured or not self._started:
            raise RuntimeError("IBKRGateway: order_sink() called while not started/configured")

        ib_order = self._build_order_ib(tracker.request)

        self._order_registry[str(tracker.request.order_id)] = tracker

        self.place_order(
            account_id=tracker.request.account_id,
            contract=tracker.contract,
            order=ib_order
        )

    def get_order_sink(self) -> Callable[..., None]:
        # TODO:LOW - Check the utility of this function (signature specially)
        return self.order_sink

    def wire_live_ticker(self, ticker_sink: Callable[[Ticker], None]):
        self.manager.set_tick_handler(ticker_sink)

    @staticmethod
    def _build_order_ib(order: "OrderRequest") -> "Order":
        if order.order_type == "MARKET":
            ib_order = MarketOrder(
                orderId=None,
                action=order.side,
                totalQuantity=order.quantity
            )
        elif order.order_type == "LIMIT":
            ib_order = LimitOrder(
                orderId=None,
                action=order.side,
                totalQuantity=order.quantity,
                lmtPrice=order.limit_price
            )
        else:
            raise ValueError(f"Unsupported order_type {order.order_type}")

        ib_order.orderRef = str(order.order_id)
        return ib_order

    # -----------------------------


    # --- Gestion des contrats ----

    def fetch_universe_snapshot(self):
        return self._ports.data_access.get_universe_snapshot()

    async def load_universe_snapshot(self) -> None:
        snapshot = self.fetch_universe_snapshot()
        id_to_contract_map = self._map_snapshot_to_ibkr_contracts(snapshot)

        await self.manager.qualify_contracts(list(id_to_contract_map.values()))

        self._contracts = {
            asset_id: contract
            for asset_id, contract in id_to_contract_map.items()
            if contract.conId > 0
        }

    @property
    def contracts(self) -> dict[str, "Contract"] :
        return self._contracts


    @staticmethod
    def _map_snapshot_to_ibkr_contracts(snapshot: UniverseSnapshot) -> dict[str, Contract]:
        contracts_map = {}
        for asset_id, ticker_data in snapshot.constituents.items():

            kwargs = {
                "symbol": ticker_data.symbol,
                "secType": ticker_data.asset_type.value,
                "exchange": getattr(ticker_data, "exchange", "SMART") or "SMART",
                "currency": getattr(ticker_data, "currency", "USD") or "USD",
            }

            if hasattr(ticker_data, "last_trade_date"):
                kwargs["lastTradeDateOrContractMonth"] = ticker_data.last_trade_date
            if hasattr(ticker_data, "strike"):
                kwargs["strike"] = ticker_data.strike
                kwargs["right"] = ticker_data.right

            contracts_map[asset_id] = Contract.create(**kwargs)

        return contracts_map



    # --- Wrappers de Contrôle ---

    async def start_streaming(self) -> None:
        contracts = list(self._contracts.values())
        await self.manager.start_streaming(contracts)

    async def pause_streaming(self) -> None:
        await self.manager.pause()

    async def resume_streaming(self) -> None:
        await self.manager.resume()

    async def stop_streaming(self) -> None:
        await self.manager.stop_streaming()

    # ---------------------------------

    # ---- API ------------------------
    async def get_account_summary(self) -> None:
        await self.manager.get_account_state()

    def place_order(self, account_id: str, contract: "Contract", order: "Order") -> None:
        client = self.manager.get_client_by_id(account_id)
        client.place_order(contract=contract, order=order)

    # ---------------------------------

    # ----- Handler ------------
    def _extract_ids(self, trade: "Trade"):
        order = trade.order
        perm_id = order.permId
        tracker = self._order_registry[order.orderRef]
        portfolio_id = tracker.request.portfolio_id
        account_id = tracker.request.account_id
        return tracker, perm_id, portfolio_id, account_id

    def _on_order_status(self, trade: Trade):
        tracker, perm_id, portfolio_id, account_id = self._extract_ids(trade)

        self._update_order_in_db(trade, perm_id, portfolio_id, account_id)

        tracker.apply_status(
            ib_order_id=trade.order.permId,
            status=trade.orderStatus.status,
            filled=trade.orderStatus.filled,
            remaining=trade.orderStatus.remaining,
            avg_fill_price=trade.orderStatus.avgFillPrice
        )

    def _update_order_in_db(
            self,
            trade: "Trade",
            perm_id: int,
            portfolio_id: str,
            account_id: str
    ):
        order_status = trade.orderStatus
        order = trade.order
        contract = trade.contract

        if not self._ports.data_access.order_exists(perm_id):
            self._ports.data_access.insert_order(
                order=order,
                perm_id=perm_id,
                portfolio_id=portfolio_id,
                account_id=account_id
            )

        self._ports.data_access.update_order_status(
            perm_id=perm_id,
            status=order_status.status,
            filled_quantity=order_status.filled,
            remaining_quantity=order_status.remaining,
            avg_fill_price=order_status.avgFillPrice
        )

        if order_status.status in ("Filled", "Cancelled", "Inactive", "ApiCancelled"):
            self._ports.data_access.mark_order_closed(
                trade=trade,
                con_id=contract.conId,
                portfolio_id=portfolio_id,
                account_id=account_id
            )

            # retry_order(order_id)

    def _on_fill(self, trade: "Trade", fill: "Fill"):
        tracker, perm_id, portfolio_id, account_id = self._extract_ids(trade)
        execution = fill.execution
        con_id = trade.contract.conId

        self._update_fill_in_db(
            execution=execution,
            fill=fill,
            account_id=account_id,
            portfolio_id=portfolio_id,
            con_id=con_id
        )

        tracker.state.apply_fill(
            filled=execution.shares,
            remaining=max(tracker.state.remaining_quantity - execution.shares, 0),
            avg_price=execution.avgPrice
        )

    def _update_fill_in_db(
            self,
            *,
            execution,
            fill,
            account_id: str,
            portfolio_id: str,
            con_id: int
    ):
        self._ports.data_access.insert_execution(
            execution=execution,
            account_id=account_id,
            portfolio_id=portfolio_id,
            con_id=con_id
        )

        self._ports.data_access._update_lots(
            execution=execution,
            portfolio_id=portfolio_id,
            con_id=con_id
        )

        self._ports.data_access._insert_position(
            portfolio_id=portfolio_id,
            account_id=account_id,
            con_id=con_id
        )

        self._ports.data_access.update_portfolio_ledger(
            execution=execution,
            commission=getattr(fill, "commissionReport", None),
            account_id=account_id,
            portfolio_id=portfolio_id,
            con_id=con_id
        )


    def _on_commission(self, trade: "Trade", fill: "Fill", commission: "CommissionReport"):
        tracker, perm_id, portfolio_id, account_id = self._extract_ids(trade)
        execution = fill.execution
        con_id = execution.contract.conId

        self._update_commission_in_db(
            execution=execution,
            commission=commission,
            account_id=account_id,
            portfolio_id=portfolio_id,
            con_id=con_id
        )

    def _update_commission_in_db(
        self,
        *,
        execution,
        commission,
        account_id: str,
        portfolio_id: str,
        con_id: int
    ):
        self._ports.data_access.update_portfolio_ledger(
            execution=execution,
            commission=commission,
            account_id=account_id,
            portfolio_id=portfolio_id,
            con_id=con_id
        )





_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance




