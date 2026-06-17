from __future__ import annotations

import logging
import queue
import time
from datetime import datetime, timezone
from collections import deque
from typing import Any


from heavenly_capital.core.thread import get_thread_manager


class LogService:

    def __init__(self, db_service):
        self._db = db_service

        self.queue: "queue.Queue[logging.LogRecord]" = queue.Queue()
        self.log_buffer = deque(maxlen=30)

        self.logger = logging.getLogger("LogService")
        self.logger.setLevel(logging.INFO)

        self.worker = LogWorker(self.queue, self.log_buffer, db_service)

    def _log(self, level: int, message: str, extra: dict | None = None):

        now = datetime.now(timezone.utc)

        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
            extra={**(extra or {}), "timestamp": now}
        )

        self.queue.put(record)

        format_log = self.format_console_line(record)
        self.log_buffer.append(format_log)

    @staticmethod
    def format_console_line(record: logging.LogRecord) -> str:
        timestamp = getattr(record, "timestamp", datetime.now(timezone.utc))
        ts_str = timestamp.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm
        domain = getattr(record, "domain", "SYSTEM")
        return f"[{record.levelname}][{ts_str}] [{domain}] {record.getMessage()}"

    def info(self, message: str, extra: dict | None = None) -> None:
        self._log(logging.INFO, message, extra)

    def error(self, message: str, extra: dict | None = None) -> None:
        self._log(logging.ERROR, message, extra)



class LogWorker:

    def __init__(self, _queue, log_buffer, db_service, name="LogWorker"):

        self.queue = _queue
        self.log_buffer = log_buffer
        self.db = db_service

        tm = get_thread_manager()
        tm.register_thread(name=name, target=self._run, daemon=True)
        tm.start_thread(name)

    def _run(self, stop_event):

        batch = []
        batch_size = 100
        flush_interval = 1.0
        last_flush = time.time()

        while not stop_event.is_set():

            try:
                record = self.queue.get(timeout=0.2)

                timestamp = getattr(record, "timestamp", datetime.now(timezone.utc))
                domain = getattr(record, "domain", "SYSTEM")
                event = getattr(record, "event", "generic")
                account_id = getattr(record, "account_id", None)
                portfolio_id = getattr(record, "portfolio_id", None)
                environment = getattr(record, "environment", None)
                metadata = {
                    k: v
                    for k, v in record.__dict__.items()
                    if k not in {
                        "name", "msg", "args", "levelname", "levelno",
                        "pathname", "filename", "module", "exc_info",
                        "exc_text", "stack_info", "lineno", "funcName",
                        "created", "msecs", "relativeCreated", "taskName",
                        "thread", "threadName", "processName", "process",
                        "timestamp", "domain", "event",
                        "account_id", "portfolio_id", "environment"
                    }
                }

                if not metadata:
                    metadata = None

                batch.append({
                    "timestamp": timestamp,
                    "level": record.levelname,
                    "domain": domain,
                    "event": event,
                    "message": record.getMessage(),
                    "account_id": account_id,
                    "portfolio_id": portfolio_id,
                    "environment": environment,
                    "metadata": metadata
                })

                now = time.time()

                if len(batch) >= batch_size or (batch and now - last_flush >= flush_interval):
                    self.db.writer.persist_logs(batch)
                    batch.clear()
                    last_flush = now

            except queue.Empty:
                continue

        if batch:
            self.db.writer.persist_logs(batch)





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
