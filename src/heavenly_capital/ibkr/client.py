import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Iterable, Callable

from ib_async import IB, Stock, Ticker, Contract  #from ibpai Stock ?




# open -n '/Users/paul/Applications/IB Gateway 10.37/IB Gateway 10.37.app'


class PermissionLevel(Enum):
    MASTER = "MASTER"
    STANDARD = "STANDARD"

class AccountType(Enum):
    LIVE = "LIVE"
    PAPER = "PAPER"

class ClientState(Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"

@dataclass
class ClientStatus:
    state: ClientState
    session_name: str
    account_type: AccountType
    permission_level: PermissionLevel



class IBKRSessionRegistry:
    def __init__(self, clients: Iterable["IBKRClient"]):
        self._clients: Dict[str, IBKRClient] = {
            c.session_name: c for c in clients
        }

        self._validate()

    def _validate(self):
        masters = [
            c for c in self._clients.values()
            if c.permission_level == PermissionLevel.MASTER
        ]

        # TODO:MEDIUM - Handle this error properly
        if len(masters) == 0:
            raise RuntimeError("No MASTER session defined")

        if len(masters) > 1:
            raise RuntimeError("Multiple MASTER sessions detected")


    def get(self, session_name: str) -> "IBKRClient":
        return self._clients[session_name]

    def get_master(self) -> "IBKRClient":
        for c in self._clients.values():
            if c.permission_level == PermissionLevel.MASTER:
                return c
        raise RuntimeError("MASTER session not found")

    def get_by_account_type(self, account_type: AccountType) -> list["IBKRClient"]:
        return [
            c for c in self._clients.values()
            if c.account_type == account_type
        ]

    @property
    def all(self) -> list["IBKRClient"]:
        return list(self._clients.values())



class IBKRClient:
    def __init__(
        self,
        client_id: int,
        session_name: str,
        host: str,
        port: int,
        account_type: str,
        permission_level: str
    ):

        self.client_id = client_id
        self.session_name = session_name
        self.host = host
        self.port = port

        self.account_type = AccountType(account_type)
        self.permission_level = PermissionLevel(permission_level)

        self._ib_client: Optional[IB] = None
        self._main_task: Optional[asyncio.Task] = None

        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._running = False

        self.status = ClientStatus(
            state=ClientState.STOPPED,
            session_name=session_name,
            account_type=self.account_type,
            permission_level=self.permission_level
        )


    # ---------------------
    # Lifecycle
    # ---------------------

    async def start(self):
        if self._running:
            return
        try:
            self._ib_client = IB(session_name=self.session_name)
            await self._ib_client.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id
            )

        except ConnectionError:
            # TODO: HIGHEST ADD SHUTDOWN HERE
            return


        self._running = True
        self._stop_event.clear()
        self._main_task = asyncio.create_task(self._run())

        self.status.state = ClientState.RUNNING


    async def stop(self):
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        self.status.state = ClientState.STOPPED

        # stop main task
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        # disconnect client
        if self._ib_client:
            if self._ib_client.isConnected():
                self._ib_client.disconnect()
            self._ib_client = None


    async def wait(self):
        await self._stop_event.wait()

    async def pause(self):
        self._pause_event.clear()
        self.status.state = ClientState.PAUSED

    async def resume(self):
        self._pause_event.set()
        self.status.state = ClientState.RUNNING


    # ---------------------
    # Main Task Run Loop
    # ---------------------

    async def _run(self):
        try:
            while not self._stop_event.is_set():
                await self._pause_event.wait()
                await asyncio.sleep(1)
                # main run task

        except asyncio.CancelledError:
            pass



class ClientManager:
    def __init__(self, configs: list[dict]):
        self._registry = self._load_configs(configs)
        self._heartbeat_task: Optional[asyncio.Task] = None
        self.on_tick: Optional[Callable[[Ticker], None]] = None

        self.tickers: dict[int, "Ticker"] = {}


    @staticmethod
    def _load_configs(configs: list[dict]) -> IBKRSessionRegistry:
        clients = []
        for cfg in configs:
            if cfg.get("enable", False):
                client = IBKRClient(
                    client_id=len(clients)+1,
                    session_name=cfg["session_name"],
                    host=cfg["host"],
                    port=cfg["port"],
                    account_type=cfg["account_type"],
                    permission_level=cfg["permission_level"]
                )
                clients.append(client)

        return IBKRSessionRegistry(clients)

    def _setup_master_session(self):
        self.master: "IBKRClient" = self._registry.get_master()
        self.master._ib_client.reqMarketDataType(1)


    async def _broadcast(self, method_name: str):
        tasks = [getattr(c, method_name)() for c in self._registry.all]
        return await asyncio.gather(*tasks)

    async def start(self):
        await self._broadcast("start")
        self._setup_master_session()

    async def stop(self):
        await self._broadcast("stop")

    async def wait(self):
        await self._broadcast("wait")

    async def pause(self):
        await self._broadcast("pause")
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def resume(self):
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            finally:
                self._heartbeat_task = None

        await self._broadcast("resume")

    @property
    def all(self) -> list["IBKRClient"]:
        return self._registry.all

    @property
    def paper_sessions(self) -> list["IBKRClient"]:
        return self._registry.get_by_account_type(AccountType.PAPER)

    async def qualify_contracts(self, contracts: list[Contract]) -> list[Contract]:
        return await self.master._ib_client.qualifyContractsAsync(*contracts)

    def set_tick_handler(self, on_tick: Callable):
        self.on_tick = on_tick

    def _on_ticker_update(self, ticker: Ticker):
        if self.on_tick:
            self.on_tick(ticker)

    async def start_streaming(self, contracts: list[Contract]):
        for contract in contracts:
            ticker = self.master._ib_client.reqMktData(
                contract=contract,
                genericTickList='',
                snapshot=False,
                regulatorySnapshot=False
            )

            ticker.updateEvent += self._on_ticker_update
            self.tickers[contract.conId] = ticker

    async def stop_streaming(self):
        for ticker in self.tickers.values():
            try:
                ticker.updateEvent -= self._on_ticker_update
                self.master._ib_client.cancelMktData(ticker.contract)
            except Exception :
                pass

        self.tickers.clear()


    async def _heartbeat(self):
        try :
            while True :
                await asyncio.sleep(5)
                try:
                    server_time = await self.master._ib_client.reqCurrentTimeAsync()

                except Exception:
                # TODO:MEDIUM Handle this shutdown (RESTART), if server_time = None
                    pass

        except asyncio.CancelledError:
            raise