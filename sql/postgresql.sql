CREATE TYPE session_mode AS ENUM ('LIVE', 'PAPER');

CREATE TABLE trading.session_registry (
    id SERIAL PRIMARY KEY,
    session_name TEXT NOT NULL,
    account_id CHAR(9) NOT NULL UNIQUE,
    mode session_mode NOT NULL,
    context JSONB
);


CREATE TABLE trading.portfolio_registry (
    id SERIAL PRIMARY KEY,
    account_id CHAR(9) NOT NULL
        REFERENCES trading.session_registry(account_id) ON DELETE CASCADE,
    portfolio_id TEXT NOT NULL UNIQUE,
    strategy_id TEXT NOT NULL,
    portfolio_name TEXT NOT NULL ,
    initial_capital NUMERIC(15,3) DEFAULT 0.0,
    currency CHAR(3) DEFAULT 'EUR',
    enabled BOOLEAN DEFAULT TRUE,

    UNIQUE(account_id, portfolio_id),
    UNIQUE(portfolio_id)
);

CREATE TABLE trading.portfolio_capital (
    id BIGSERIAL PRIMARY KEY,
    account_id CHAR(9) NOT NULL,
    portfolio_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN (
        'INITIAL_CAPITAL', 'CAPITAL_ADDITION', 'CAPITAL_WITHDRAWAL'
    )),
    amount NUMERIC(18,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (portfolio_id, type, created_at),

    FOREIGN KEY (account_id, portfolio_id)
        REFERENCES trading.portfolio_registry(account_id, portfolio_id)
        ON DELETE CASCADE
);



CREATE TABLE trading.orders (
    id BIGSERIAL PRIMARY KEY,                  -- ID interne unique
    perm_id BIGINT NOT NULL UNIQUE,
    account_id CHAR(9) NOT NULL,
    portfolio_id TEXT NOT NULL,
    con_id BIGINT NOT NULL,

    -- Ordre de base
    action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL')), -- Buy ou Sell
    order_type TEXT NOT NULL,                 -- MKT, LMT, etc.
    tif TEXT,                                 -- Time in force (DAY, GTC...)
    quantity NUMERIC(15,3) NOT NULL,          -- Quantité demandée
    lmt_price NUMERIC(15,4),                  -- Prix limite (si applicable)
    aux_price NUMERIC(15,4),                  -- Prix auxiliaire (ex : stop)
    oca_type INT,                             -- OCA group type
    oca_group TEXT,                           -- OCA group name
    order_ref TEXT,                           -- Référence externe

    -- Tracking execution
    status TEXT NOT NULL,                       -- Status actuel (Submitted, Filled, Cancelled)
    filled_quantity NUMERIC(15,3) DEFAULT 0,    -- Quantité déjà exécutée
    remaining_quantity NUMERIC(15,3) DEFAULT 0, -- Quantité restante
    avg_fill_price NUMERIC(15,4) DEFAULT 0,     -- Moyenne prix des fills

    -- Champs IBKR optionnels
    reference_price_type INT DEFAULT 0,      -- Pegged to Market / Primary

    created_at TIMESTAMPTZ DEFAULT NOW(),    -- Timestamp création
    updated_at TIMESTAMPTZ DEFAULT NOW(),    -- Timestamp mise à jour

    -- Foreign Keys
    FOREIGN KEY (account_id)
        REFERENCES trading.session_registry(account_id)
        ON DELETE CASCADE,

    FOREIGN KEY (account_id, portfolio_id)
        REFERENCES trading.portfolio_registry(account_id, portfolio_id)
        ON DELETE CASCADE,

    FOREIGN KEY (con_id)
        REFERENCES trading.contracts(con_id)
        ON DELETE RESTRICT
);


CREATE TABLE trading.executions (
    id BIGSERIAL PRIMARY KEY,                               -- ID interne unique
    exec_id TEXT NOT NULL UNIQUE,
    perm_id BIGINT NOT NULL,
    account_id CHAR(9) NOT NULL,
    portfolio_id TEXT NOT NULL,
    con_id BIGINT NOT NULL,

    side TEXT NOT NULL CHECK (side IN ('BOT', 'SLD')),      -- Buy / Sell
    shares NUMERIC(15,3) NOT NULL,                          -- Quantité exécutée
    price NUMERIC(15,4) NOT NULL,                           -- Prix de l’exécution
    execution_time TIMESTAMPTZ NOT NULL,                    -- Timestamp de l’exécution
    cum_qty NUMERIC(15,4),                                  -- Quantité cumulée sur l’ordre (optionnel)
    avg_price NUMERIC(15,4),                                -- Prix moyen cumulatif sur l’ordre (optionnel)
    last_liquidity INT DEFAULT 0,                           -- Type de liquidité (IBKR)
    pending_price_revision BOOLEAN DEFAULT FALSE,           -- Révision de prix en attente

    created_at TIMESTAMPTZ DEFAULT NOW(),                   -- Timestamp insertion dans DB

    -- Foreign Keys
    FOREIGN KEY (perm_id)
        REFERENCES trading.orders(perm_id)
        ON DELETE CASCADE,

    FOREIGN KEY (account_id)
        REFERENCES trading.session_registry(account_id)
        ON DELETE CASCADE,

    FOREIGN KEY (account_id, portfolio_id)
        REFERENCES trading.portfolio_registry(account_id, portfolio_id)
        ON DELETE CASCADE,

    FOREIGN KEY (con_id)
        REFERENCES contracts(con_id)
        ON DELETE RESTRICT
);


CREATE TABLE trading.positions (
    account_id CHAR(9) NOT NULL,
    portfolio_id TEXT NOT NULL,
    con_id BIGINT NOT NULL,
    quantity NUMERIC(15,3) NOT NULL,
    avg_cost NUMERIC(15,4) NOT NULL,
    market_price NUMERIC(15,4),
    market_value NUMERIC(15,4),
    unrealized_pnl NUMERIC(15,4),
    realized_pnl NUMERIC(15,4),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (account_id, portfolio_id, con_id),

    FOREIGN KEY (account_id, portfolio_id)
        REFERENCES trading.portfolio_registry(account_id, portfolio_id)
        ON DELETE CASCADE,

    FOREIGN KEY (con_id)
        REFERENCES trading.contracts(con_id)
        ON DELETE RESTRICT
);


CREATE TABLE trading.trade_lots (
    id BIGSERIAL PRIMARY KEY,                     -- Identifiant unique du lot
    portfolio_id TEXT NOT NULL,                   -- Portefeuille auquel appartient le lot
    con_id BIGINT NOT NULL,                       -- Contrat acheté
    buy_exec_id TEXT NOT NULL REFERENCES trading.executions(exec_id), -- Exécution d'achat
    open_quantity NUMERIC(15,3) NOT NULL,        -- Quantité encore ouverte
    closed_quantity NUMERIC(15,3) DEFAULT 0,     -- Quantité déjà vendue
    price NUMERIC(15,4) NOT NULL,                -- Prix d'achat par unité
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (portfolio_id, buy_exec_id),

    FOREIGN KEY (portfolio_id)
        REFERENCES trading.portfolio_registry(portfolio_id)
        ON DELETE CASCADE,

    FOREIGN KEY (con_id)
        REFERENCES trading.contracts(con_id)
        ON DELETE RESTRICT
);


CREATE TABLE trading.trade_lot_consumption (
    id BIGSERIAL PRIMARY KEY,                     -- Identifiant unique de consommation
    lot_id BIGINT NOT NULL REFERENCES trading.trade_lots(id) ON DELETE CASCADE, -- Lot consommé
    sell_exec_id TEXT NOT NULL REFERENCES trading.executions(exec_id),             -- Exécution de vente partielle
    quantity NUMERIC(15,3) NOT NULL,             -- Quantité vendue depuis ce lot
    realized_pnl NUMERIC(15,4) NOT NULL,         -- PnL réalisé sur cette portion
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (sell_exec_id, lot_id)
);



CREATE TABLE trading.portfolio_ledger (
    id BIGSERIAL PRIMARY KEY,
    account_id CHAR(9) NOT NULL,
    portfolio_id TEXT NOT NULL,

    con_id BIGINT,                               -- null si opération cash pure
    exec_id TEXT NOT NULL REFERENCES trading.executions(exec_id),    -- null si pas lié à une execution
    type TEXT NOT NULL CHECK (type IN (
        'TRADE_DEBIT', 'TRADE_CREDIT', 'COMMISSION',
        'REALIZED_PNL', 'DIVIDEND', 'FX'
    )),

    amount NUMERIC(15,4) NOT NULL,
    currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (exec_id, type),

    FOREIGN KEY (account_id)
        REFERENCES trading.session_registry(account_id)
        ON DELETE CASCADE,

    FOREIGN KEY (account_id, portfolio_id)
        REFERENCES trading.portfolio_registry(account_id, portfolio_id)
        ON DELETE CASCADE,

    FOREIGN KEY (con_id)
        REFERENCES trading.contracts(con_id)
        ON DELETE RESTRICT
);



CREATE TABLE trading.contracts (
    con_id BIGINT PRIMARY KEY,
    instrument_id BIGINT,
    symbol TEXT NOT NULL,
    sec_type TEXT NOT NULL, -- STK, OPT, FUT...
    exchange TEXT,
    primary_exchange TEXT,
    currency CHAR(3) NOT NULL,
    local_symbol TEXT,
    trading_class TEXT,

    FOREIGN KEY (instrument_id)
        REFERENCES trading.instruments(instrument_id)
        ON DELETE CASCADE
);


CREATE TABLE trading.instruments (
    instrument_id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    currency CHAR(3) NOT NULL,
    long_name TEXT,
    sector TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE trading.universes (
    universe_id SMALLSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- 'SP500', 'NASDAQ100'
    name TEXT NOT NULL
);

INSERT INTO trading.universes (code, name) VALUES
('SP500', 'S&P 500'),
('NASDAQ100', 'Nasdaq 100');



CREATE TABLE trading.universe_membership (
    membership_id BIGSERIAL PRIMARY KEY,
    instrument_id BIGINT NOT NULL,
    universe_id SMALLINT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE, -- NULL = actif
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    FOREIGN KEY (instrument_id)
        REFERENCES trading.instruments (instrument_id)
        ON DELETE CASCADE,

    FOREIGN KEY (universe_id)
        REFERENCES trading.universes (universe_id)
        ON DELETE CASCADE
);

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE trading.universe_membership
ADD CONSTRAINT no_overlap
EXCLUDE USING gist (
    instrument_id WITH =,
    universe_id WITH =,
    daterange(valid_from, COALESCE(valid_to, 'infinity')) WITH &&
);



CREATE TABLE trading.portfolio_targets (
    target_id BIGSERIAL PRIMARY KEY,
    account_id CHAR(9) NOT NULL,
    portfolio_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    rebalance_date DATE NOT NULL,
    tolerance NUMERIC(6,5) NOT NULL DEFAULT 0.02,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (account_id, portfolio_id, rebalance_date),

    FOREIGN KEY (account_id, portfolio_id)
        REFERENCES trading.portfolio_registry(account_id, portfolio_id)
        ON DELETE CASCADE
);

CREATE TABLE trading.portfolio_target_weights (
    target_id BIGINT NOT NULL,
    con_id BIGINT NOT NULL,
    target_weight NUMERIC(9,6) NOT NULL
        CHECK (target_weight >= 0 AND target_weight <= 1),

    PRIMARY KEY (target_id, con_id),

    FOREIGN KEY (target_id)
        REFERENCES trading.portfolio_targets(target_id)
        ON DELETE CASCADE,

    FOREIGN KEY (con_id)
        REFERENCES trading.contracts(con_id)
        ON DELETE RESTRICT
);



CREATE TABLE trading.account_margins (
    id SERIAL PRIMARY KEY,
    account_id CHAR(9) NOT NULL,
    currency CHAR(3) NOT NULL,
    equity_with_loan NUMERIC(15,4),
    full_available_funds NUMERIC(15,4),
    full_excess_liquidity NUMERIC(15,4),
    full_init_margin_req NUMERIC(15,4),
    full_maint_margin_req NUMERIC(15,4),
    gross_position_value NUMERIC(15,4),
    net_liquidation NUMERIC(15,4),
    total_cash_value NUMERIC(15,4),
    buying_power NUMERIC(15,4),
    cushion NUMERIC(15,6),
    lookahead_next_change BIGINT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(account_id, currency),

    FOREIGN KEY (account_id)
        REFERENCES trading.session_registry(account_id)
        ON DELETE CASCADE
);


CREATE TABLE trading.account_balances (
    id SERIAL PRIMARY KEY,
    account_id CHAR(9) NOT NULL,
    currency CHAR(3) NOT NULL,
    total_cash_balance NUMERIC(15,4),
    accrued_cash NUMERIC(15,4),
    net_liquidation_by_currency NUMERIC(15,4),
    stock_market_value NUMERIC(15,4),
    unrealized_pnl NUMERIC(15,4),
    realized_pnl NUMERIC(15,4),
    exchange_rate NUMERIC(15,4),
    net_dividend NUMERIC(15,4),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(account_id, currency),

    FOREIGN KEY (account_id)
        REFERENCES trading.session_registry(account_id)
        ON DELETE CASCADE
);

CREATE TABLE trading.portfolio_balances (
    portfolio_id TEXT PRIMARY KEY,
    account_id CHAR(9) NOT NULL,
    currency CHAR(3) DEFAULT 'USD',
    total_cash_balance NUMERIC(18,4) DEFAULT 0,
    stock_market_value NUMERIC(18,4) NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC(18,4) DEFAULT 0,
    realized_pnl NUMERIC(18,4) DEFAULT 0,
    total_commissions NUMERIC(18,4) DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
--     net_dividend NUMERIC(18,4) DEFAULT 0,

    UNIQUE(account_id, portfolio_id),

    FOREIGN KEY (portfolio_id)
        REFERENCES trading.portfolio_registry(portfolio_id)
        ON DELETE CASCADE
);


CREATE TABLE trading.models_registry (
    id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_type TEXT NOT NULL CHECK (model_type IN ('BUY','SELL','STOP_LOSS')),
    version NUMERIC(2,1) NOT NULL CHECK (version > 0),
    path TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(model_name, version)
);


CREATE TABLE trading.portfolio_models (
    portfolio_id TEXT NOT NULL,
    model_type TEXT NOT NULL CHECK (
        model_type IN ('BUY','SELL','STOP_LOSS')
    ),

    model_name TEXT NOT NULL,
    version NUMERIC(3,1) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (portfolio_id, model_type),

    FOREIGN KEY (portfolio_id)
        REFERENCES trading.portfolio_registry(portfolio_id)
        ON DELETE CASCADE,

    FOREIGN KEY (model_name, version)
        REFERENCES trading.models_registry(model_name, version)
        ON DELETE RESTRICT
);


CREATE TABLE trading.model_records (
    id BIGSERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    version NUMERIC(3,1) NOT NULL,
    con_id BIGINT NOT NULL,

    trading_day DATE NOT NULL,
    step SMALLINT NOT NULL,
    decision BOOLEAN NOT NULL,
    forced BOOLEAN NOT NULL DEFAULT FALSE,
    score DOUBLE PRECISION,
    penalty DOUBLE PRECISION,
    prediction_ts BIGINT,
    output_at DOUBLE PRECISION NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(model_name, version, con_id, trading_day, step)
);


CREATE TABLE trading.feature_registry (
    uid TEXT PRIMARY KEY,
    category TEXT,
    plugin TEXT,
    scope TEXT,
    kind TEXT,
    fields TEXT,
    freqs JSONB,
    params JSONB,
    priority INT,
    cache BOOLEAN,
    is_active BOOLEAN DEFAULT TRUE
);

 -- TODO:LOW add unique constraint on priority label

CREATE TABLE trading.market_day_session (
    session_id UUID PRIMARY KEY NOT NULL,

    session_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
    phase TEXT NOT NULL CHECK (phase IN ('STRATEGIC_SETUP','PRE_MARKET','IN_MARKET','POST_MARKET')),
    state TEXT NOT NULL CHECK (state IN ('RUNNING','DONE')),
    error BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (session_date)
);






-- DROP TABLE IF EXISTS trading.portfolio_registry CASCADE;
-- DROP TABLE IF EXISTS trading.portfolio_capital CASCADE;
-- DROP TABLE IF EXISTS trading.session_registry CASCADE;
-- DROP TABLE IF EXISTS trading.contracts CASCADE;
-- DROP TABLE IF EXISTS trading.orders CASCADE;
-- DROP TABLE IF EXISTS trading.executions CASCADE;
-- DROP TABLE IF EXISTS trading.positions CASCADE;
-- DROP TABLE IF EXISTS trading.trade_lots CASCADE;
-- DROP TABLE IF EXISTS trading.trade_lot_consumption CASCADE;
-- DROP TABLE IF EXISTS trading.portfolio_ledger CASCADE;

-- DROP TABLE IF EXISTS trading.instruments CASCADE;
-- DROP TABLE IF EXISTS trading.universes CASCADE;
-- DROP TABLE IF EXISTS trading.universe_membership CASCADE;


-- DROP TABLE IF EXISTS trading.portfolio_targets CASCADE;
-- DROP TABLE IF EXISTS trading.portfolio_target_weights CASCADE;

-- DROP TABLE IF EXISTS trading.account_balances CASCADE;
-- DROP TABLE IF EXISTS trading.portfolio_balances CASCADE;
-- DROP TABLE IF EXISTS trading.account_margins CASCADE;

-- DROP TABLE IF EXISTS trading.models_registry CASCADE;
-- DROP TABLE IF EXISTS trading.portfolio_models CASCADE;
-- DROP TABLE IF EXISTS trading.model_records CASCADE;
-- DROP TABLE IF EXISTS trading.feature_registry CASCADE;

-- DROP TABLE IF EXISTS trading.market_day_session CASCADE;

-- DROP TYPE IF EXISTS session_mode;