-- reset_portfolio_position.sql
-- Script de commodité dev
-- Paramètres : :portfolio_id, :date, :initial_cash

DO $$
DECLARE
    v_portfolio_id  TEXT    := 'portfolio_01';
    v_date          DATE    := '2026-06-30';
    v_initial_cash  NUMERIC :=  425083.64;


BEGIN

    -- 1. portfolio_ledger SANS filtre de date (référence toutes les executions)
    DELETE FROM trading.portfolio_ledger
    WHERE portfolio_id = v_portfolio_id;

    -- 2. trade_lots SANS filtre de date (cascade → trade_lot_consumption)
    DELETE FROM trading.trade_lots
    WHERE portfolio_id = v_portfolio_id;

    -- 3. orders SANS filtre de date (cascade → executions)
    DELETE FROM trading.orders
    WHERE portfolio_id = v_portfolio_id;

    -- 4. positions
    DELETE FROM trading.positions
    WHERE portfolio_id = v_portfolio_id;

    -- 5. portfolio_balances
    UPDATE trading.portfolio_balances
    SET total_cash_balance = v_initial_cash,
        stock_market_value = 0,
        unrealized_pnl     = 0,
        realized_pnl       = 0,
        total_commissions  = 0,
        updated_at         = NOW()
    WHERE portfolio_id = v_portfolio_id;

    -- 6. portfolio_targets (cascade → portfolio_target_weights)
    DELETE FROM trading.portfolio_targets
    WHERE portfolio_id = v_portfolio_id
      AND rebalance_date = v_date;

    -- 7. market_day_session
    DELETE FROM trading.market_day_session
    WHERE session_date = v_date;

END $$;