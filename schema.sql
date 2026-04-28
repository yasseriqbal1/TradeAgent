-- TradeAgent Database Schema

-- Track each scan run
CREATE TABLE IF NOT EXISTS scan_runs (
    id SERIAL PRIMARY KEY,
    scan_type VARCHAR(20) NOT NULL,  -- 'premarket' or 'validation'
    run_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL,  -- 'success', 'failed', 'partial'
    top_n INT,
    stocks_scanned INT,
    error_message TEXT,
    execution_time_seconds FLOAT
);

-- Store signals for each scan
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

-- Store detailed factors
CREATE TABLE IF NOT EXISTS factors (
    id SERIAL PRIMARY KEY,
    signal_id INT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    -- Raw factors
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
    -- Normalized factors (z-scores)
    z_momentum FLOAT,
    z_volatility FLOAT,
    z_volume FLOAT,
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_scan_runs_timestamp ON scan_runs(run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_scan_runs_type ON scan_runs(scan_type);
CREATE INDEX IF NOT EXISTS idx_signals_scan_run ON signals(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_rank ON signals(rank);
CREATE INDEX IF NOT EXISTS idx_factors_signal ON factors(signal_id);

-- ============================================================================
-- PAPER / LIVE BOT TRADE LOGGING (trades_history)
-- ============================================================================

-- Trade blotter for bot actions (supports fractional shares)
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

-- ============================================================================
-- LIVE TRADING TABLES (Phase 3A)
-- ============================================================================

-- Live trading signals with trade plans
CREATE TABLE IF NOT EXISTS live_signals (
    id SERIAL PRIMARY KEY,
    scan_run_id INT REFERENCES scan_runs(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    composite_score FLOAT NOT NULL,
    price FLOAT NOT NULL,
    signal_type VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'
    -- Trade plan
    shares DOUBLE PRECISION NOT NULL,
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    max_hold_days INT NOT NULL,
    -- Metadata
    rank INT,
    market_regime VARCHAR(20),
    scan_type VARCHAR(20),
    executed BOOLEAN DEFAULT FALSE,
    order_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Order tracking
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(50) PRIMARY KEY,  -- UUID
    ticker VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'
    quantity DOUBLE PRECISION NOT NULL,
    order_type VARCHAR(20) NOT NULL,  -- 'market', 'limit', 'stop_loss', etc.
    status VARCHAR(20) NOT NULL,  -- 'pending', 'submitted', 'filled', 'cancelled', etc.
    -- Pricing
    limit_price FLOAT,
    stop_price FLOAT,
    filled_price FLOAT,
    filled_quantity DOUBLE PRECISION DEFAULT 0,
    remaining_quantity DOUBLE PRECISION,
    commission FLOAT DEFAULT 0,
    -- Execution
    created_at TIMESTAMP DEFAULT NOW(),
    submitted_at TIMESTAMP,
    filled_at TIMESTAMP,
    -- References
    signal_id VARCHAR(50),
    notes TEXT
);

-- Active positions
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    quantity DOUBLE PRECISION NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_date TIMESTAMP NOT NULL DEFAULT NOW(),
    current_price FLOAT NOT NULL,
    -- Exit parameters
    stop_loss FLOAT NOT NULL,
    take_profit FLOAT NOT NULL,
    max_hold_days INT NOT NULL,
    -- P&L
    unrealized_pnl FLOAT DEFAULT 0,
    unrealized_pnl_pct FLOAT DEFAULT 0,
    position_value FLOAT,
    -- References
    entry_order_id VARCHAR(50),
    stop_order_id VARCHAR(50),
    take_profit_order_id VARCHAR(50),
    signal_id VARCHAR(50),
    -- Metadata
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
    -- Entry
    entry_date TIMESTAMP NOT NULL,
    entry_price FLOAT NOT NULL,
    entry_order_id VARCHAR(50),
    -- Exit
    exit_date TIMESTAMP NOT NULL,
    exit_price FLOAT NOT NULL,
    exit_order_id VARCHAR(50),
    exit_reason VARCHAR(50) NOT NULL,  -- 'stop_loss', 'take_profit', 'max_hold', 'manual'
    -- Trade details
    quantity DOUBLE PRECISION NOT NULL,
    hold_days INT,
    -- P&L
    pnl FLOAT NOT NULL,
    pnl_pct FLOAT NOT NULL,
    commission FLOAT DEFAULT 0,
    -- References
    signal_id VARCHAR(50),
    position_id INT,
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Risk events
CREATE TABLE IF NOT EXISTS risk_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    severity VARCHAR(20) NOT NULL,  -- 'info', 'warning', 'critical'
    event_type VARCHAR(50) NOT NULL,  -- 'daily_loss_limit', 'position_limit', etc.
    message TEXT NOT NULL,
    data JSONB,  -- Store additional event data
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for live trading tables
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
