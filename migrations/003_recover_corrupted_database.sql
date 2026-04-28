-- Recovery migration for corrupted/missing PostgreSQL tables.
-- Usage:
--   psql -U postgres -d tradeagent -f migrations/003_recover_corrupted_database.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- Core scan tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS scan_runs (
    id SERIAL PRIMARY KEY,
    scan_type VARCHAR(20) NOT NULL,
    run_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL,
    top_n INT,
    stocks_scanned INT,
    error_message TEXT,
    execution_time_seconds FLOAT
);

CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    scan_run_id INT NOT NULL REFERENCES scan_runs(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    rank INT NOT NULL,
    composite_score FLOAT NOT NULL,
    price FLOAT,
    volume BIGINT,
    market_cap BIGINT,
    sector VARCHAR(50),
    selected BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS factors (
    id SERIAL PRIMARY KEY,
    signal_id INT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    return_5d FLOAT,
    return_10d FLOAT,
    return_20d FLOAT,
    rsi_14 FLOAT,
    ema_9 FLOAT,
    ema_21 FLOAT,
    ema_50 FLOAT,
    volatility_20d FLOAT,
    atr_14 FLOAT,
    volume_20d_avg BIGINT,
    volume_ratio FLOAT,
    z_momentum FLOAT,
    z_volatility FLOAT,
    z_volume FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Trade history (used by live bot + dashboard)
-- ---------------------------------------------------------------------------

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

-- Repair missing columns for partially-corrupted tables.
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS trade_date TIMESTAMP NOT NULL DEFAULT NOW();
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS ticker VARCHAR(10);
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS action VARCHAR(10);
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS shares FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS price FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS total_value FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(50);
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS entry_price FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS hold_duration_minutes FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS pnl FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS pnl_pct FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS capital_before FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS capital_after FLOAT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS total_positions INT;
ALTER TABLE trades_history ADD COLUMN IF NOT EXISTS notes TEXT;

-- ---------------------------------------------------------------------------
-- Live trading tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS live_signals (
    id SERIAL PRIMARY KEY,
    scan_run_id INT REFERENCES scan_runs(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    composite_score FLOAT NOT NULL,
    price FLOAT NOT NULL,
    signal_type VARCHAR(10) NOT NULL,
    shares DOUBLE PRECISION NOT NULL,
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

CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(50) PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    limit_price FLOAT,
    stop_price FLOAT,
    filled_price FLOAT,
    filled_quantity DOUBLE PRECISION DEFAULT 0,
    remaining_quantity DOUBLE PRECISION,
    commission FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    submitted_at TIMESTAMP,
    filled_at TIMESTAMP,
    signal_id VARCHAR(50),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    quantity DOUBLE PRECISION NOT NULL,
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

ALTER TABLE positions ADD COLUMN IF NOT EXISTS quantity DOUBLE PRECISION;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_price FLOAT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_date TIMESTAMP NOT NULL DEFAULT NOW();
ALTER TABLE positions ADD COLUMN IF NOT EXISTS current_price FLOAT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS stop_loss FLOAT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS take_profit FLOAT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS max_hold_days INT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS position_value FLOAT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl FLOAT DEFAULT 0;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl_pct FLOAT DEFAULT 0;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS exit_triggered BOOLEAN DEFAULT FALSE;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Ensure one row per ticker so ON CONFLICT (ticker) works reliably.
DELETE FROM positions a
USING positions b
WHERE a.ticker = b.ticker
  AND a.ctid < b.ctid;

CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_ticker_unique ON positions(ticker);

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
    quantity DOUBLE PRECISION NOT NULL,
    hold_days INT,
    pnl FLOAT NOT NULL,
    pnl_pct FLOAT NOT NULL,
    commission FLOAT DEFAULT 0,
    signal_id VARCHAR(50),
    position_id INT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    severity VARCHAR(20) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_scan_runs_timestamp ON scan_runs(run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_scan_runs_type ON scan_runs(scan_type);
CREATE INDEX IF NOT EXISTS idx_signals_scan_run ON signals(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_rank ON signals(rank);
CREATE INDEX IF NOT EXISTS idx_factors_signal ON factors(signal_id);

CREATE INDEX IF NOT EXISTS idx_trades_history_trade_date ON trades_history(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_history_ticker_date ON trades_history(ticker, trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_history_action ON trades_history(action);

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

-- ---------------------------------------------------------------------------
-- Minimal bootstrap data
-- ---------------------------------------------------------------------------

-- Seed one baseline capital record only if trade history is empty.
INSERT INTO trades_history (
    trade_date,
    ticker,
    action,
    shares,
    price,
    total_value,
    notes,
    capital_before,
    capital_after,
    total_positions
)
SELECT NOW(), 'CASH', 'INIT', 0, 0, 0, 'Bootstrap capital row after DB recovery', 100000.0, 100000.0, 0
WHERE NOT EXISTS (SELECT 1 FROM trades_history);

COMMIT;

-- Verification output
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'scan_runs',
    'signals',
    'factors',
    'trades_history',
    'live_signals',
    'orders',
    'positions',
    'live_trades',
    'risk_events'
  )
ORDER BY table_name;

SELECT
    (SELECT COUNT(*) FROM positions) AS positions_rows,
    (SELECT COUNT(*) FROM trades_history) AS trades_history_rows,
    (SELECT COUNT(*) FROM scan_runs) AS scan_runs_rows;