# from queue import Queue
# from threading import Thread
# from typing import Any, Callable
#
# from sqlalchemy import text
#
# from heavenly_capital.db.connector import DB_CONNECTOR


# class DatabaseRouter:
#     def __init__(self, db: "DBConnector"):
#         self.db = db
#         self.queue: Queue = Queue()
#         self._handlers: dict[str, Callable] = {}
#         self._worker = Thread(target=self._start_worker, daemon=True)
#
#     def worker(self):
#         while True:
#             job = self.queue.get()
#             try:
#                 with self.db.UnitOfWork(self.db.engine) as conn:
#                     handler = self._handlers.get(job["type"])
#                     if handler:
#                         handler(conn, **job["payload"])
#                     else:
#                         raise ValueError(f"No handler for job type {job['type']}")
#             finally:
#                 self.queue.task_done()
#
#     def _start_worker(self):
#         Thread(target=self.worker, daemon=True).start()
#
#     def register_handler(self, job_type: str, handler: Callable[[Any, Any], None]):
#         self._handlers[job_type] = handler
#
#     def enqueue(self, job_type: str, payload: dict):
#         self.queue.put({"type": job_type, "payload": payload})



# class DataIngestionLayer:
#
#     _queue: Queue = Queue()
#     _worker_started: bool = False
#
#     @classmethod
#     def _start_worker(cls):
#         if cls._worker_started:
#             return
#         cls._worker_started = True
#
#         def worker():
#             while True:
#                 job = cls._queue.get()
#                 try:
#                     with DB_CONNECTOR.UnitOfWork(DB_CONNECTOR.engine) as conn:
#                         query = text(job["query"])
#                         for con_id, price in job["market_snapshot"].items():
#                             conn.execute(query, {"con_id": con_id, "market_price": price})
#                 finally:
#                     cls._queue.task_done()
#
#         Thread(target=worker, daemon=True).start()
#
#     @classmethod
#     def update_market_data_in_db(cls, market_snapshot: dict[int, float]):
#         cls._start_worker()  # Démarre le worker si nécessaire
#
#         query = """
#             UPDATE positions
#             SET market_price   = :market_price,
#                 market_value   = quantity * :market_price,
#                 unrealized_pnl = (quantity * :market_price) - (quantity * avg_cost),
#                 updated_at     = NOW()
#             WHERE con_id = :con_id
#               AND :market_price IS NOT NULL
#               AND :market_price <> -1
#         """
#
#         cls._queue.put({
#             "query": query,
#             "market_snapshot": market_snapshot
#         })




from typing import Protocol, TYPE_CHECKING

from datetime import date

if TYPE_CHECKING:
    from heavenly_capital.core.system_manager import MarketDaySession

class DataIngestionLayer(Protocol):
    pass

class InMemorySessionDIL:
    def __init__(self):
        self._store = None