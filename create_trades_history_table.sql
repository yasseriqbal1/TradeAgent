-- Trades History Table
-- Logs every buy and sell transaction for analysis

CREATE TABLE IF NOT EXISTS trades_history (
    id SERIAL PRIMARY KEY,
    trade_date TIMESTAMP NOT NULL DEFAULT NOW(),
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(4) NOT NULL,  -- 'BUY' or 'SELL'
    shares DECIMAL(12, 8) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    total_value DECIMAL(10, 2) NOT NULL,
    
    -- Exit information (only for SELL)
    exit_reason VARCHAR(20),  -- 'stop_loss', 'take_profit', 'trailing_stop', 'manual'
    entry_price DECIMAL(10, 2),  -- Original buy price
    hold_duration_minutes INTEGER,  -- How long position was held
    pnl DECIMAL(10, 2),  -- Profit/loss on this trade
    pnl_pct DECIMAL(6, 2),  -- P&L percentage
    
    -- Account state at time of trade
    capital_before DECIMAL(10, 2),
    capital_after DECIMAL(10, 2),
    total_positions INTEGER,  -- Number of open positions after this trade
    
    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades_history(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_date ON trades_history(trade_date);
CREATE INDEX IF NOT EXISTS idx_trades_action ON trades_history(action);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_date ON trades_history(ticker, trade_date);

-- Useful queries:

-- Total trades by ticker
-- SELECT ticker, COUNT(*) as trade_count, 
--        SUM(CASE WHEN action='BUY' THEN 1 ELSE 0 END) as buys,
--        SUM(CASE WHEN action='SELL' THEN 1 ELSE 0 END) as sells
-- FROM trades_history GROUP BY ticker ORDER BY trade_count DESC;

-- Win/loss summary
-- SELECT 
--   COUNT(*) FILTER (WHERE pnl > 0) as wins,
--   COUNT(*) FILTER (WHERE pnl < 0) as losses,
--   AVG(pnl) as avg_pnl,
--   SUM(pnl) as total_pnl
-- FROM trades_history WHERE action='SELL';

-- Today's trades
-- SELECT * FROM trades_history 
-- WHERE trade_date >= CURRENT_DATE 
-- ORDER BY trade_date DESC;
