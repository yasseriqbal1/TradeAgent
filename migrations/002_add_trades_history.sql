-- Migration: Add trades_history table (paper/live bot trade blotter)
-- Usage: psql -d tradeagent -f migrations/002_add_trades_history.sql

BEGIN;

CREATE TABLE IF NOT EXISTS trades_history (
    id SERIAL PRIMARY KEY,
    trade_date TIMESTAMP NOT NULL DEFAULT NOW(),
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,
    shares FLOAT NOT NULL,
    price FLOAT NOT NULL,
    total_value FLOAT NOT NULL,
    exit_reason VARCHAR(50),
    entry_price FLOAT,
    hold_duration_minutes FLOAT,
    pnl FLOAT,
    pnl_pct FLOAT,
    capital_before FLOAT,
    capital_after FLOAT,
    total_positions INT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_history_trade_date ON trades_history(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_history_ticker_date ON trades_history(ticker, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_history_action ON trades_history(action);

COMMIT;

SELECT 'Migration complete! Table added:' as status;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('trades_history')
ORDER BY table_name;
