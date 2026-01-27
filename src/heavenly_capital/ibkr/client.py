import asyncio
from contextlib import suppress
from enum import IntEnum
from typing import AsyncIterator, Optional, Dict
from ibapi.contract import Contract
from ibapi.order import Order
# from ibapi.common import TickType

class TickType(IntEnum):
    # TODO:HIGHEST : Custom TickType class, find the real one ine ibapi
    BID_SIZE = 0
    BID = 1
    ASK = 2
    ASK_SIZE = 3
    LAST = 4
    LAST_SIZE = 5
    VOLUME = 6



# --- événements normalisés ---
class IBEvent:
    def __init__(self, event_type: str, payload, ib_ts: float, local_ts: float, session_id: str):
        self.event_type = event_type
        self.payload = payload
        self.ib_ts = ib_ts
        self.local_ts = local_ts
        self.session_id = session_id

class TickEvent(IBEvent): pass
class OrderStatusEvent(IBEvent): pass
class FillEvent(IBEvent): pass
class ErrorEvent(IBEvent): pass
class ConnectionEvent(IBEvent): pass
class HeartbeatEvent(IBEvent): pass
class LatencyEvent(IBEvent): pass

# --------------------------
# IBKRClient avec ib_async
# --------------------------
class IBKRClient:
    def __init__(self, client_id: int, session_name: str, host: str="127.0.0.1", port: int=4002):
        self.client_id = client_id
        self.session_name = session_name
        self.host = host
        self.port = port

        # état connection
        self._connected: bool = False

        # queues d'événements
        self._events_queue: asyncio.Queue[IBEvent] = asyncio.Queue(maxsize=1000)

        # heartbeat / latency
        self._heartbeat_ts: Optional[float] = None
        self._latency_ms: Optional[float] = None

        # reqId / orderId internes
        self._req_id_counter = 1
        self._order_id_counter = 1

        # subscriptions
        self._subscriptions: Dict[int, Contract] = {}

        # async tasks
        self._loop = asyncio.get_event_loop()
        self._main_task: Optional[asyncio.Task] = None

        # ib_async client placeholder
        self._ib_client = None  # sera remplacé dans start()

    # ---------------------
    # Lifecycle
    # ---------------------
    async def start(self):
        """Démarre la connexion ib_async et la boucle de dispatch"""
        from ib_async import IB  # import ici pour éviter dépendance globale
        self._ib_client = IB()
        await self._ib_client.connectAsync(host=self.host, port=self.port, clientId=self.client_id)
        self._connected = True

        # subscribe callbacks
        self._ib_client.errorEvent += self._on_error
        self._ib_client.orderStatusEvent += self._on_order_status
        # self._ib_client.fillEvent += self._on_fill
        # self._ib_client.tickEvent += self._on_tick
        # self._ib_client.connectionClosedEvent += self._on_connection_closed

        self._main_task = self._loop.create_task(self._run())

    async def stop(self):
        self._connected = False
        if self._main_task:
            self._main_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._main_task
        if self._ib_client and self._ib_client.isConnected():
            await self._ib_client.disconnectAsync()

    def is_connected(self) -> bool:
        return self._connected

    # ---------------------
    # Orders
    # ---------------------
    async def send_order(self, order: Order, contract: Contract) -> int:
        order_ref = self._order_id_counter
        self._order_id_counter += 1
        # envoi via ib_async
        await self._ib_client.placeOrderAsync(order_ref, contract, order)
        return order_ref

    async def cancel_order(self, order_ref: int):
        await self._ib_client.cancelOrderAsync(order_ref)

    async def replace_order(self, order_ref: int, new_order: Order):
        await self._ib_client.cancelOrderAsync(order_ref)
        await self.send_order(new_order, new_order.contract)  # assume contract inclus

    # ---------------------
    # Market Data
    # ---------------------
    async def subscribe_ticks(self, contract: Contract) -> int:
        sub_id = self._req_id_counter
        self._req_id_counter += 1
        self._subscriptions[sub_id] = contract
        await self._ib_client.reqMktDataAsync(sub_id, contract)
        return sub_id

    async def unsubscribe_ticks(self, subscription_id: int):
        contract = self._subscriptions.pop(subscription_id, None)
        if contract:
            await self._ib_client.cancelMktDataAsync(subscription_id)

    async def request_historical(self, contract: Contract, spec: dict):
        req_id = self._req_id_counter
        self._req_id_counter += 1
        await self._ib_client.reqHistoricalDataAsync(req_id, contract, **spec)

    # ---------------------
    # Event Stream
    # ---------------------
    async def events(self) -> AsyncIterator[IBEvent]:
        while self._connected:
            event: IBEvent = await self._events_queue.get()
            yield event

    # ---------------------
    # Supervision
    # ---------------------
    @property
    def last_heartbeat_ts(self) -> Optional[float]:
        return self._heartbeat_ts

    @property
    def current_latency_ms(self) -> Optional[float]:
        return self._latency_ms

    # ---------------------
    # Internal Run Loop
    # ---------------------
    async def _run(self):
        """Heartbeat et monitoring"""
        while self._connected:
            await asyncio.sleep(1)
            now = self._loop.time()
            self._heartbeat_ts = now
            event = HeartbeatEvent(
                event_type="heartbeat",
                payload=None,
                ib_ts=now,
                local_ts=now,
                session_id=self.session_name
            )
            await self._push_event(event)

    async def _push_event(self, event: IBEvent):
        try:
            self._events_queue.put_nowait(event)
        except asyncio.QueueFull:
            # drop le plus ancien si plein
            _ = self._events_queue.get_nowait()
            await self._events_queue.put(event)

    # ---------------------
    # IB Async Callbacks → IBEvent
    # ---------------------
    def _on_error(self, reqId, errorCode, errorString):
        event = ErrorEvent(
            event_type="error",
            payload={"reqId": reqId, "code": errorCode, "msg": errorString},
            ib_ts=self._loop.time(),
            local_ts=self._loop.time(),
            session_id=self.session_name
        )
        asyncio.create_task(self._push_event(event))

    def _on_order_status(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        payload = {
            "orderId": orderId,
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice
        }
        event = OrderStatusEvent(
            event_type="order_status",
            payload=payload,
            ib_ts=self._loop.time(),
            local_ts=self._loop.time(),
            session_id=self.session_name
        )
        asyncio.create_task(self._push_event(event))

    def _on_fill(self, fill):
        event = FillEvent(
            event_type="fill",
            payload=fill,
            ib_ts=self._loop.time(),
            local_ts=self._loop.time(),
            session_id=self.session_name
        )
        asyncio.create_task(self._push_event(event))

    def _on_tick(self, tick):
        event = TickEvent(
            event_type="tick",
            payload=tick,
            ib_ts=self._loop.time(),
            local_ts=self._loop.time(),
            session_id=self.session_name
        )
        asyncio.create_task(self._push_event(event))

    def _on_connection_closed(self):
        event = ConnectionEvent(
            event_type="connection_closed",
            payload=None,
            ib_ts=self._loop.time(),
            local_ts=self._loop.time(),
            session_id=self.session_name
        )
        asyncio.create_task(self._push_event(event))
        self._connected = False
