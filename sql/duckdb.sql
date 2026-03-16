-- DROP TABLE IF EXISTS ohlcv_5s;

INSTALL postgres;
LOAD postgres;

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
    ask_tick_count BIGINT,

    UNIQUE(instrument_id, ts_start),

    CHECK (
    (last_open IS NOT NULL AND last_open >= 0) AND
    (last_high IS NOT NULL AND last_high >= 0) AND
    (last_low IS NOT NULL AND last_low >= 0) AND
    (last_close IS NOT NULL AND last_close >= 0) AND
    (last_volume IS NOT NULL AND last_volume >= 0) AND
    (last_tick_count IS NOT NULL AND last_tick_count >= 0) AND
    (bid_open IS NOT NULL AND bid_open >= 0) AND
    (bid_high IS NOT NULL AND bid_high >= 0) AND
    (bid_low IS NOT NULL AND bid_low >= 0) AND
    (bid_close IS NOT NULL AND bid_close >= 0) AND
    (bid_volume IS NOT NULL AND bid_volume >= 0) AND
    (bid_tick_count IS NOT NULL AND bid_tick_count >= 0) AND
    (ask_open IS NOT NULL AND ask_open >= 0) AND
    (ask_high IS NOT NULL AND ask_high >= 0) AND
    (ask_low IS NOT NULL AND ask_low >= 0) AND
    (ask_close IS NOT NULL AND ask_close >= 0) AND
    (ask_volume IS NOT NULL AND ask_volume >= 0) AND
    (ask_tick_count IS NOT NULL AND ask_tick_count >= 0)
)
);


CREATE INDEX idx_ohlcv_5s_instrument_ts
ON ohlcv_5s (instrument_id, ts_start);


