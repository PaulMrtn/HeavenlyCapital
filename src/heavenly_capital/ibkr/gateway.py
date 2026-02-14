from __future__ import annotations

from datetime import timezone
from typing import Optional, Any, Callable, TYPE_CHECKING

from ib_async import Contract, Ticker

from heavenly_capital.core.runtime_config import IBKRConfig, AsyncRuntimeModule
from heavenly_capital.ibkr.client import ClientManager
from heavenly_capital.models.market_data import TickEvent
from heavenly_capital.models.tickers import UniverseSnapshot

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import SystemPorts


CLIENTS_CONFIG = [
    {
        "session_name": "SESSION_1",
        "host": "127.0.0.1",
        "port": 4002,
        "enable": True,
        "account_type": "PAPER",         # LIVE ou PAPER
        "permission_level": "MASTER"    # MASTER ou STANDARD
    },
    {
        "session_name": "SESSION_2",
        "host": "127.0.0.1",
        "port": 4003,
        "enable": True,
        "account_type": "PAPER",
        "permission_level": "STANDARD"
    },

]

UTC_ZONE = timezone.utc


class TickFeeder:
    def __init__(self, sink: Optional[Callable[["TickEvent"], None]]):
        self.sink = sink

    def handle(self, ticker: Ticker):
        if ticker.last <= 0 and ticker.bid <= 0 and ticker.ask <= 0:
            return

        event = TickEvent(
            symbol=ticker.contract.symbol,
            conId=ticker.contract.conId,
            last=ticker.last,
            last_size=ticker.lastSize,
            bid=ticker.bid,
            bid_size=ticker.bidSize,
            ask=ticker.ask,
            ask_size=ticker.askSize,
            volume=ticker.volume,
            timestamp=ticker.timestamp
        )

        if self.sink:
            self.sink(event)


class IBKRGateway(AsyncRuntimeModule):

    def __init__(self) -> None:
        self._configured: bool = False
        self._started: bool = False

        self._config: Optional["IBKRConfig"] = None
        self._ports: Optional["SystemPorts"] = None

        self.manager: Optional["ClientManager"] = None
        self._contracts: Optional[dict[str, "Contract"]] = None

        # TODO : MOCK sent order (update with OrderObject)
        self._mock_sent_orders: list[dict[str, Any]] = list()
        self.tick_feeder: Optional["TickFeeder"] = None


    def configure(self, *, config: "IBKRConfig", ports: "SystemPorts") -> None:
        self._config = config
        self._ports = ports

        self.manager = ClientManager(CLIENTS_CONFIG) # config.sessions
        self.tick_feeder = TickFeeder(sink=None)

        self.manager.set_tick_handler(self.tick_feeder.handle)

        self._configured = True

    async def start(self) -> None:
        if not self._configured:
            raise RuntimeError("IBKRGateway: start() called before configure()")
        await self.manager.start()
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
        return {
            "is_healthy": True,
        }


    # --- MOCK SINK API ----------

    def order_sink(self, session_key, order: dict[str, Any]) -> None:
        # TODO: créer un objet Order contenant toutes les infos de TradingSessionKey et supprimer session-key en input.
        # Appliquer symétriquement la modification
        if not self._configured or not self._started:
            raise RuntimeError("IBKRGateway: order_sink() called while not started/configured")

        self._mock_sent_orders.append(order)

    def get_order_sink(self) -> Callable[[dict[str, Any]], None]:
        return self.order_sink

    def wire_tick_sink(self, sink: Callable[["TickEvent"], None]):
        if self.tick_feeder is None:
            raise RuntimeError("Gateway: tick_feeder must be initialized before wiring.")

        self.tick_feeder.sink = sink

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

    async def get_account_summary(self) -> None:
        await self.manager.get_account_state()



_instance: Optional[IBKRGateway] = None

def get_ibkr_gateway() -> IBKRGateway:
    global _instance
    if _instance is None:
        _instance = IBKRGateway()
    return _instance




