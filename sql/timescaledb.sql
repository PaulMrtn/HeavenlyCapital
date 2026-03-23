-- CREATE SCHEMA IF NOT EXISTS market;

-- DROP TABLE IF EXISTS market.ohlcv_5s;

CREATE TABLE market.ohlcv_5s (
    instrument_id BIGINT NOT NULL,
    ts_start TIMESTAMPTZ NOT NULL,
    ts_end TIMESTAMPTZ NOT NULL,

    last_open DOUBLE PRECISION NOT NULL CHECK (last_open >= 0),
    last_high DOUBLE PRECISION NOT NULL CHECK (last_high >= 0),
    last_low DOUBLE PRECISION NOT NULL CHECK (last_low >= 0),
    last_close DOUBLE PRECISION NOT NULL CHECK (last_close >= 0),
    last_volume DOUBLE PRECISION NOT NULL CHECK (last_volume >= 0),
    last_tick_count BIGINT NOT NULL CHECK (last_tick_count >= 0),

    bid_open DOUBLE PRECISION NOT NULL CHECK (bid_open >= 0),
    bid_high DOUBLE PRECISION NOT NULL CHECK (bid_high >= 0),
    bid_low DOUBLE PRECISION NOT NULL CHECK (bid_low >= 0),
    bid_close DOUBLE PRECISION NOT NULL CHECK (bid_close >= 0),
    bid_volume DOUBLE PRECISION NOT NULL CHECK (bid_volume >= 0),
    bid_tick_count BIGINT NOT NULL CHECK (bid_tick_count >= 0),

    ask_open DOUBLE PRECISION NOT NULL CHECK (ask_open >= 0),
    ask_high DOUBLE PRECISION NOT NULL CHECK (ask_high >= 0),
    ask_low DOUBLE PRECISION NOT NULL CHECK (ask_low >= 0),
    ask_close DOUBLE PRECISION NOT NULL CHECK (ask_close >= 0),
    ask_volume DOUBLE PRECISION NOT NULL CHECK (ask_volume >= 0),
    ask_tick_count BIGINT NOT NULL CHECK (ask_tick_count >= 0),

    PRIMARY KEY (instrument_id, ts_start),

    -- Contrainte combinée : jours ouvrés + heures US
    CONSTRAINT chk_market_hours_weekdays CHECK (
        EXTRACT(DOW FROM ts_start AT TIME ZONE 'America/New_York') BETWEEN 1 AND 5
        AND
        EXTRACT(HOUR FROM ts_start AT TIME ZONE 'America/New_York') +
        EXTRACT(MINUTE FROM ts_start AT TIME ZONE 'America/New_York') / 60
        BETWEEN 4.0 AND 20.0
    )
);

SELECT create_hypertable(
    'market.ohlcv_5s',
    'ts_start',
    chunk_time_interval => interval '1 day',
    create_default_indexes => FALSE
);

ALTER TABLE market.ohlcv_5s SET (
    timescaledb.compress_segmentby = 'instrument_id',
    timescaledb.orderby = 'ts_start DESC'
);

CALL add_columnstore_policy('market.ohlcv_5s', after => INTERVAL '1 day');

CREATE INDEX idx_ohlcv_5s_ts_end
ON market.ohlcv_5s (ts_end);


-- CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
