from typing import Any

from sqlalchemy import text

from heavenly_capital.db.connector import DBConnector
from heavenly_capital.core.thread import get_thread_manager, ThreadTarget

DB_THREAD_NAME = "db_worker"


class DataIngestionLayer:

    def __init__(self, connector: DBConnector):
        self._connector = connector
        self._worker = get_thread_manager()


    def submit_job(self, fn, *args, **kwargs):
        self._worker.submit(DB_THREAD_NAME, fn, *args, **kwargs)

    def _run_in_uow(self, fn, *args, **kwargs):
        with self._connector.UnitOfWork(self._connector.engine) as conn:
            fn(conn, *args, **kwargs)

    def persist_bars(self, bars_dict: dict[int, dict[str, Any]]):
        if not bars_dict:
            return

        self.submit_job(self._persist_bars_impl, bars_dict)

    def _persist_bars_impl(self, conn, bars_dict: dict[int, dict[str, Any]]):
        rows = []
        excluded_values = {-1, None}

        for instrument_id, ohlc_dict in bars_dict.items():
            last = ohlc_dict['last']
            bid = ohlc_dict['bid']
            ask = ohlc_dict['ask']

            row_data = {
                "instrument_id": instrument_id,
                "ts_start": last.ts_start,
                "ts_end": last.ts_end,
                "last_open": last.open,
                "last_high": last.high,
                "last_low": last.low,
                "last_close": last.close,
                "last_volume": last.volume,
                "last_tick_count": last.tick_count,
                "bid_open": bid.open,
                "bid_high": bid.high,
                "bid_low": bid.low,
                "bid_close": bid.close,
                "bid_volume": bid.volume,
                "bid_tick_count": bid.tick_count,
                "ask_open": ask.open,
                "ask_high": ask.high,
                "ask_low": ask.low,
                "ask_close": ask.close,
                "ask_volume": ask.volume,
                "ask_tick_count": ask.tick_count,
            }

            if not any(value in excluded_values for value in row_data.values()):
                rows.append(row_data)

        if not rows:
            return

        insert_sql = """
            INSERT INTO market.ohlcv_5s (instrument_id, ts_start, ts_end,
                                          last_open, last_high, last_low, last_close, last_volume,
                                          last_tick_count,
                                          bid_open, bid_high, bid_low, bid_close, bid_volume, bid_tick_count,
                                          ask_open, ask_high, ask_low, ask_close, ask_volume, ask_tick_count)
            VALUES (:instrument_id,
                    to_timestamp(:ts_start),
                    to_timestamp(:ts_end),
                    :last_open, :last_high, :last_low, :last_close, :last_volume, :last_tick_count,
                    :bid_open, :bid_high, :bid_low, :bid_close, :bid_volume, :bid_tick_count,
                    :ask_open, :ask_high, :ask_low, :ask_close, :ask_volume, :ask_tick_count)
            ON CONFLICT (instrument_id, ts_start) DO NOTHING
        """

        conn.execute(text(insert_sql), rows)