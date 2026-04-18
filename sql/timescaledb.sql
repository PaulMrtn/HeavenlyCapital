-- Intraday Price Live

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



-- Daily Price History

CREATE TYPE market.price_adjustment AS ENUM (
    'TOTAL_PRICE',
    'TOTAL_RETURN'
);

CREATE TABLE market.prices_daily (
    instrument_id BIGINT NOT NULL,
    date DATE NOT NULL,
    adjustment_type market.price_adjustment NOT NULL,

    open NUMERIC(12,6) NOT NULL,
    high NUMERIC(12,6) NOT NULL,
    low NUMERIC(12,6) NOT NULL,
    close NUMERIC(12,6) NOT NULL,

    volume NUMERIC,
    turnover NUMERIC,

    unadjusted_close NUMERIC(12,6),
    dividend NUMERIC(12,6),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (instrument_id, date, adjustment_type),

    FOREIGN KEY (instrument_id)
        REFERENCES trading.instruments(instrument_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_prices_filter
ON market.prices_daily (adjustment_type, date, instrument_id);


-- ALTER TABLE market.prices_daily
-- ADD CONSTRAINT chk_prices_daily_ohlc CHECK (
--     low <= open AND
--     low <= close AND
--     high >= open AND
--     high >= close AND
--     high >= low
-- );

ALTER TABLE market.prices_daily
ADD CONSTRAINT chk_prices_daily_positive CHECK (
    open > 0 AND high > 0 AND low > 0 AND close > 0
);

ALTER TABLE market.prices_daily
ADD CONSTRAINT chk_prices_daily_nonneg CHECK (
    (volume IS NULL OR volume >= 0) AND
    (turnover IS NULL OR turnover >= 0)
);




-- CREATE SCHEMA IF NOT EXISTS market;
-- DROP TABLE IF EXISTS market.ohlcv_5s;
-- DROP TABLE IF EXISTS market.prices_daily;

-- CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;