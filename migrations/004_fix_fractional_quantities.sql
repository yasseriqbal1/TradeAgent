-- Migration: Fix fractional share support for position/order/trade quantity fields
-- Usage: psql -d tradeagent -f migrations/004_fix_fractional_quantities.sql

BEGIN;

-- Use DOUBLE PRECISION for fractional-share quantities.
ALTER TABLE IF EXISTS live_signals
    ALTER COLUMN shares TYPE DOUBLE PRECISION USING shares::DOUBLE PRECISION;

ALTER TABLE IF EXISTS orders
    ALTER COLUMN quantity TYPE DOUBLE PRECISION USING quantity::DOUBLE PRECISION;

ALTER TABLE IF EXISTS orders
    ALTER COLUMN filled_quantity TYPE DOUBLE PRECISION USING filled_quantity::DOUBLE PRECISION;

ALTER TABLE IF EXISTS orders
    ALTER COLUMN remaining_quantity TYPE DOUBLE PRECISION USING remaining_quantity::DOUBLE PRECISION;

ALTER TABLE IF EXISTS positions
    ALTER COLUMN quantity TYPE DOUBLE PRECISION USING quantity::DOUBLE PRECISION;

ALTER TABLE IF EXISTS live_trades
    ALTER COLUMN quantity TYPE DOUBLE PRECISION USING quantity::DOUBLE PRECISION;

-- Backfill rows previously truncated to 0 by integer casting.
UPDATE positions
SET quantity = position_value / NULLIF(current_price, 0)
WHERE COALESCE(quantity, 0) = 0
  AND position_value IS NOT NULL
  AND current_price IS NOT NULL
  AND current_price <> 0;

COMMIT;

SELECT 'Fractional quantity migration complete' AS status;