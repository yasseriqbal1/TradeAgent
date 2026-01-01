-- Phase 3A Migration: Add Live Trading Tables
-- Run this to add live trading tables to existing database
-- Usage: psql -d tradeagent -f migrations/001_add_live_trading_tables.sql

BEGIN;

-- Live trading signals with trade plans
CREATE TABLE IF NOT EXISTS live_signals (
    id SERIAL PRIMARY KEY,
    scan_run_id INT REFERENCES scan_runs(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    composite_score FLOAT NOT NULL,
    price FLOAT NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    shares INT NOT NULL,
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    max_hold_days INT NOT NULL,
    rank INT,
    market_regime VARCHAR(20),
    scan_type VARCHAR(20),
    executed BOOLEAN DEFAULT FALSE,
    order_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Order tracking
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(50) PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity INT NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    limit_price FLOAT,
    stop_price FLOAT,
    filled_price FLOAT,
    filled_quantity INT DEFAULT 0,
    remaining_quantity INT,
    commission FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    submitted_at TIMESTAMP,
    filled_at TIMESTAMP,
    signal_id VARCHAR(50),
    notes TEXT
);

-- Active positions
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    quantity INT NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_date TIMESTAMP NOT NULL DEFAULT NOW(),
    current_price FLOAT NOT NULL,
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    max_hold_days INT NOT NULL,
    unrealized_pnl FLOAT DEFAULT 0,
    unrealized_pnl_pct FLOAT DEFAULT 0,
    position_value FLOAT,
    entry_order_id VARCHAR(50),
    stop_order_id VARCHAR(50),
    take_profit_order_id VARCHAR(50),
    signal_id VARCHAR(50),
    notes TEXT,
    exit_triggered BOOLEAN DEFAULT FALSE,
    exit_reason VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Completed trades
CREATE TABLE IF NOT EXISTS live_trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    entry_date TIMESTAMP NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_order_id VARCHAR(50),
    exit_date TIMESTAMP NOT NULL,
    exit_price FLOAT NOT NULL,
    exit_order_id VARCHAR(50),
    exit_reason VARCHAR(50) NOT NULL,
    quantity INT NOT NULL,
    hold_days INT,
    pnl FLOAT NOT NULL,
    pnl_pct FLOAT NOT NULL,
    commission FLOAT DEFAULT 0,
    signal_id VARCHAR(50),
    position_id INT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Risk events
CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    severity VARCHAR(20) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_live_signals_ticker ON live_signals(ticker);
CREATE INDEX IF NOT EXISTS idx_live_signals_timestamp ON live_signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_live_signals_executed ON live_signals(executed);
CREATE INDEX IF NOT EXISTS idx_orders_ticker ON orders(ticker);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions(ticker);
CREATE INDEX IF NOT EXISTS idx_positions_entry_date ON positions(entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_live_trades_ticker ON live_trades(ticker);
CREATE INDEX IF NOT EXISTS idx_live_trades_exit_date ON live_trades(exit_date DESC);
CREATE INDEX IF NOT EXISTS idx_live_trades_exit_reason ON live_trades(exit_reason);
CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity);
CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events(event_type);

COMMIT;

-- Verify tables created
SELECT 'Migration complete! Tables added:' as status;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('live_signals', 'orders', 'positions', 'live_trades', 'risk_events')
ORDER BY table_name;
