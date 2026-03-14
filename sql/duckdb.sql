-- DROP TABLE IF EXISTS ohlcv_5s;

-- INSTALL postgres;
-- LOAD postgres;

ATTACH 'host=localhost dbname=trading_state_dev user=app_rw_local'
AS postgres_db (TYPE POSTGRES);


CREATE TABLE ohlcv_5s (
    instrument_id BIGINT NOT NULL,
    ts_start DOUBLE PRECISION NOT NULL,
    ts_end DOUBLE PRECISION NOT NULL,

    -- Last price
    last_open DOUBLE PRECISION,
    last_high DOUBLE PRECISION,
    last_low DOUBLE PRECISION,
    last_close DOUBLE PRECISION,
    last_volume DOUBLE PRECISION,
    last_tick_count BIGINT,

    -- Bid price
    bid_open DOUBLE PRECISION,
    bid_high DOUBLE PRECISION,
    bid_low DOUBLE PRECISION,
    bid_close DOUBLE PRECISION,
    bid_volume DOUBLE PRECISION,
    bid_tick_count BIGINT,

    -- Ask price
    ask_open DOUBLE PRECISION,
    ask_high DOUBLE PRECISION,
    ask_low DOUBLE PRECISION,
    ask_close DOUBLE PRECISION,
    ask_volume DOUBLE PRECISION,
    ask_tick_count BIGINT

    UNIQUE(instrument_id, ts_start)
);


CREATE INDEX idx_ohlcv_5s_instrument_ts
ON ohlcv_5s (instrument_id, ts_start);