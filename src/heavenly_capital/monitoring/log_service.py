from __future__ import annotations

from datetime import datetime

import logging
import queue
from typing import Any
from collections import deque

from heavenly_capital.core.thread import get_thread_manager


class NullLogService:

    @staticmethod
    def info(message: str, **fields: Any) -> None:
        if fields:
            print(f"[INFO] {message} | {fields}")
        else:
            print(f"[INFO] {message}")

    def error(self, message: str, **fields: Any) -> None:
        if fields:
            print(f"[ERROR] {message} | {fields}")
        else:
            print(f"[ERROR] {message}")





class LogService:
    def __init__(self, db_service):
        self._db = db_service
        self.queue = queue.Queue()
        self.log_buffer = deque(maxlen=30)

        self.logger = logging.getLogger("AsyncLogService")
        self.logger.setLevel(logging.INFO)

    def _log(self, level: int, message: str, **fields: Any):
        now = datetime.utcnow()  # TODO:LOW nake sure all time in the app are in the same timezone
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
            extra={**fields, "timestamp": now}
        )
        self.queue.put(record)
        self.log_buffer.append(f"[{level}][{now.isoformat()}] {message}")

    def info(self, message: str, **fields: Any) -> None:
        self._log(logging.INFO, message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, **fields)



class LogWorker:
    def __init__(self, name: str = "LogWorker", max_console_logs: int = 30, db_handler: Optional[object] = None):
        self.name = name
        self.queue: "queue.Queue[logging.LogRecord]" = queue.Queue()
        self.log_buffer: deque[str] = deque(maxlen=max_console_logs)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

        self.db_handler = db_handler
        self.console_handler: logging.Handler | None = None

        tm = get_thread_manager()
        tm.register_thread(name=name, target=self._run, daemon=True)

    def _run(self, stop_event):
        batch: list[dict] = []
        batch_size = 100
        flush_interval = 1.0
        import time
        last_flush = time.time()

        while not stop_event.is_set():
            try:
                record = self.queue.get(timeout=0.2)
                if record is None:  # Sentinel pour shutdown
                    break

                # Mise à jour buffer console
                timestamp = getattr(record, "timestamp", datetime.utcnow())
                self.log_buffer.append(f"[{record.levelname}][{timestamp.isoformat()}] {record.getMessage()}")

                # Préparer batch pour DB
                if self.db_handler:
                    log_dict = {
                        "timestamp": timestamp,
                        "level": record.levelname,
                        "domain": getattr(record, "domain", "SYSTEM"),
                        "event": getattr(record, "event", "generic"),
                        "message": record.getMessage(),
                        "account_id": getattr(record, "account_id", None),
                        "portfolio_id": getattr(record, "portfolio_id", None),
                        "environment": getattr(record, "environment", None),
                        "metadata": getattr(record, "metadata", {}),
                    }
                    batch.append(log_dict)

                # Flush batch si nécessaire
                now = time.time()
                if self.db_handler and (len(batch) >= batch_size or (batch and now - last_flush >= flush_interval)):
                    self.db_handler.persist_logs(batch)
                    batch.clear()
                    last_flush = now

                # Console handler direct si défini
                if self.console_handler:
                    self.console_handler.emit(record)

            except queue.Empty:
                continue

        # Flush final avant shutdown
        if self.db_handler and batch:
            self.db_handler.persist_logs(batch)

    def put(self, record: logging.LogRecord):
        # Injecter timestamp si absent
        if not hasattr(record, "timestamp"):
            record.timestamp = datetime.utcnow()
        self.queue.put(record)


