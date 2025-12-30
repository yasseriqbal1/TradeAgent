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
