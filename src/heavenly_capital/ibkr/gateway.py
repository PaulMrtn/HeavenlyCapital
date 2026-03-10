from __future__ import annotations

from datetime import timezone
from typing import Optional, Any, Callable, TYPE_CHECKING

from ib_async import Contract, Ticker, Trade, Order, MarketOrder, LimitOrder, Fill, CommissionReport

from heavenly_capital.core.runtime_config import IBKRConfig, AsyncRuntimeModule
from heavenly_capital.core.session_manager import TradingSessionKey
from heavenly_capital.ibkr.client import ClientManager
from heavenly_capital.models.order import OrderTracker, OrderRequest, TrackerEventContext
from heavenly_capital.models.tickers import UniverseSnapshot, TickerUniverseSnapshot

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts


from heavenly_capital.data.db_mock import TradingSessionDB

tsDB = TradingSessionDB()


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

    def _wrap_event(self, handler):
        def wrapper(*args, **kwargs):
            try:
                return handler(*args, **kwargs)
            except Exception as e:
                import traceback
                traceback.print_exc()

        return wrapper

    async def start(self) -> None:
        if not self._configured:
            raise RuntimeError("IBKRGateway: start() called before configure()")
        await self.manager.start()

        for client in self.manager.all:
            client.events.order_status = self._wrap_event(self._on_order_status)
            client.events.exec_details = self._wrap_event(self._on_fill)
            client.events.commission_report = self._wrap_event(self._on_commission)


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

# Check si dans l'objet OGR cette fonction qui compatible (nouvelle signature)

    def order_sink(self, session_key: "TradingSessionKey", tracker: "OrderTracker") -> None:
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
        # TODO:WARNING update with all type of Order and all of type of attribut
        if order.order_type == "MKT":
            ib_order = MarketOrder(
                orderId=None,
                action=order.side,
                totalQuantity=order.quantity,
                tif='DAY'
            )
        elif order.order_type == "LMT":
            ib_order = LimitOrder(
                orderId=None,
                action=order.side,
                totalQuantity=order.quantity,
                lmtPrice=order.limit_price,
                tif='DAY'
            )
            ib_order.outsideRth = True

        else:
            raise ValueError(f"Unsupported order_type {order.order_type}")

        ib_order.orderRef = str(order.order_id)
        return ib_order

    # -----------------------------


    # --- Gestion des contrats ----

    @staticmethod
    def get_universe_snapshot(universe_id: str) -> UniverseSnapshot:
        # TODO: MEDIUM Move this function in the correct module
        contracts = tsDB.fetch_instruments()
        constituents = {}

        for c in contracts:
            snapshot = TickerUniverseSnapshot(
                symbol=c["symbol"],
                asset_type=c["sec_type"],
                name=c["long_name"],
                sector=c["sector"],
                con_id=c["con_id"],
                exchange=c.get("exchange") or "SMART",
                currency=c.get("currency") or "USD",
                primary_exchange=c.get("primary_exchange")
            )
            constituents[snapshot.con_id] = snapshot

        return UniverseSnapshot(
            universe_id=universe_id,
            constituents=constituents
        )
    async def load_universe_snapshot(self) -> None:
        snapshot = self.get_universe_snapshot("SP500 Sample")
        id_to_contract_map = self._map_snapshot_to_ibkr_contracts(snapshot)

        await self.manager.qualify_contracts(list(id_to_contract_map.values()))

        self._contracts = {
            asset_id: contract
            for asset_id, contract in id_to_contract_map.items()
            if contract.conId > 0
        }

    @property
    def contracts(self) -> dict[str, Contract] | None:
        return self._contracts

    @staticmethod
    def _map_snapshot_to_ibkr_contracts(snapshot: UniverseSnapshot):
        contracts_map = {}
        for con_id, ticker_data in snapshot.constituents.items():
            kwargs = {
                "symbol": ticker_data.symbol,
                "secType": ticker_data.asset_type,
                "exchange": getattr(ticker_data, "exchange", "SMART") or "SMART",
                "currency": getattr(ticker_data, "currency", "USD") or "USD"
            }
            contracts_map[con_id] = Contract.create(**kwargs)

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

    # TODO: WARNING Get Cash and other information about account
    async def update_account_state(self) -> None:
        accounts = await self.manager.get_account_state()

        for account in accounts:
            tsDB.update_account_state_in_db(account)

    def place_order(self, account_id: str, contract: "Contract", order: "Order") -> None:
        client = self.manager.get_client_by_id(account_id)
        client.place_order(contract=contract, order=order)

    # ---------------------------------

    # ----- Handler -------------------

    def _build_event_context(self, trade: "Trade") -> "TrackerEventContext":
        order = trade.order
        tracker = self._order_registry[order.orderRef]
        return TrackerEventContext(
            tracker=tracker,
            perm_id=order.permId,
            portfolio_id=tracker.request.portfolio_id,
            account_id=tracker.request.account_id
        )

    def _on_order_status(self, trade: Trade):
        ctx = self._build_event_context(trade)
        ctx.tracker.apply_status(
            trade=trade,
            context=ctx
        )

    def _on_fill(self, trade: "Trade", fill: "Fill"):
        ctx = self._build_event_context(trade)
        ctx.tracker.state.apply_fill(
            trade=trade,
            fill=fill,
            context=ctx
        )

    def _on_commission(self, trade: "Trade", fill: "Fill", commission: "CommissionReport"):
        ctx = self._build_event_context(trade)
        ctx.tracker.state.apply_commission(
            execution=fill.execution,
            commission=commission,
            context=ctx
        )

    # ---------------------------------


_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance





    # async def update_portfolio_state(self) -> None:
    #     portfolios = await self.manager.get_portfolio_state()
    #
    #     for portfolio in portfolios:
    #         print(portfolio)

