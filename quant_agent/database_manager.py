"""
Database Manager for Live Trading
Simple wrapper for PostgreSQL operations
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Simple database manager for live trading tables"""
    
    def __init__(self, connection_string: str):
        """
        Initialize database manager
        
        Args:
            connection_string: PostgreSQL connection string
        """
        self.connection_string = connection_string
        self.conn = None
    
    def connect(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            logger.info("Database connected")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            logger.info("Database disconnected")
    
    def _execute(self, query: str, params: tuple = None, fetch: bool = False):
        """Execute query"""
        if not self.conn:
            self.connect()
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Query failed: {e}")
            raise
    
    # Live Signals
    def save_live_signal(self, signal: Dict) -> int:
        """Save live signal to database"""
        query = """
            INSERT INTO live_signals 
            (scan_run_id, ticker, timestamp, composite_score, price, signal_type,
             shares, stop_loss, take_profit, max_hold_days, rank, market_regime, scan_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            signal.get('scan_run_id'),
            signal['ticker'],
            signal['timestamp'],
            signal['composite_score'],
            signal['price'],
            signal['signal_type'],
            signal['shares'],
            signal['stop_loss'],
            signal['take_profit'],
            signal['max_hold_days'],
            signal.get('rank'),
            signal.get('market_regime'),
            signal.get('scan_type')
        )
        result = self._execute(query, params, fetch=True)
        return result[0]['id'] if result else None
    
    def get_unexecuted_signals(self) -> List[Dict]:
        """Get signals that haven't been executed"""
        query = "SELECT * FROM live_signals WHERE executed = FALSE ORDER BY timestamp DESC"
        return self._execute(query, fetch=True)
    
    def mark_signal_executed(self, signal_id: int, order_id: str):
        """Mark signal as executed"""
        query = "UPDATE live_signals SET executed = TRUE, order_id = %s WHERE id = %s"
        self._execute(query, (order_id, signal_id))
    
    # Orders
    def save_order(self, order: Dict):
        """Save order to database"""
        query = """
            INSERT INTO orders 
            (id, ticker, side, quantity, order_type, status, limit_price, stop_price,
             filled_price, filled_quantity, remaining_quantity, commission,
             created_at, submitted_at, filled_at, signal_id, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                filled_price = EXCLUDED.filled_price,
                filled_quantity = EXCLUDED.filled_quantity,
                filled_at = EXCLUDED.filled_at
        """
        params = (
            order['id'],
            order['ticker'],
            order['side'],
            order['quantity'],
            order['order_type'],
            order['status'],
            order.get('limit_price'),
            order.get('stop_price'),
            order.get('filled_price'),
            order.get('filled_quantity', 0),
            order.get('remaining_quantity'),
            order.get('commission', 0),
            order.get('created_at'),
            order.get('submitted_at'),
            order.get('filled_at'),
            order.get('signal_id'),
            order.get('notes')
        )
        self._execute(query, params)
    
    def get_orders(self, status: str = None, ticker: str = None) -> List[Dict]:
        """Get orders, optionally filtered"""
        query = "SELECT * FROM orders WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = %s"
            params.append(status)
        if ticker:
            query += " AND ticker = %s"
            params.append(ticker)
        
        query += " ORDER BY created_at DESC"
        return self._execute(query, tuple(params), fetch=True)
    
    # Positions
    def save_position(self, position: Dict):
        """Save or update position"""
        query = """
            INSERT INTO positions 
            (ticker, quantity, entry_price, entry_date, current_price, stop_loss,
             take_profit, max_hold_days, unrealized_pnl, unrealized_pnl_pct,
             position_value, entry_order_id, signal_id, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker) DO UPDATE SET
                current_price = EXCLUDED.current_price,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                unrealized_pnl_pct = EXCLUDED.unrealized_pnl_pct,
                position_value = EXCLUDED.position_value,
                updated_at = NOW()
        """
        params = (
            position['ticker'],
            position['quantity'],
            position['entry_price'],
            position['entry_date'],
            position['current_price'],
            position['stop_loss'],
            position['take_profit'],
            position['max_hold_days'],
            position.get('unrealized_pnl', 0),
            position.get('unrealized_pnl_pct', 0),
            position.get('position_value'),
            position.get('entry_order_id'),
            position.get('signal_id'),
            position.get('notes')
        )
        self._execute(query, params)
    
    def get_active_positions(self) -> List[Dict]:
        """Get all active positions"""
        query = "SELECT * FROM positions ORDER BY entry_date DESC"
        return self._execute(query, fetch=True)
    
    def delete_position(self, ticker: str):
        """Delete position (after closing)"""
        query = "DELETE FROM positions WHERE ticker = %s"
        self._execute(query, (ticker,))
    
    # Trades
    def save_trade(self, trade: Dict) -> int:
        """Save completed trade"""
        query = """
            INSERT INTO live_trades 
            (ticker, entry_date, entry_price, entry_order_id, exit_date, exit_price,
             exit_order_id, exit_reason, quantity, hold_days, pnl, pnl_pct,
             commission, signal_id, position_id, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        params = (
            trade['ticker'],
            trade['entry_date'],
            trade['entry_price'],
            trade.get('entry_order_id'),
            trade['exit_date'],
            trade['exit_price'],
            trade.get('exit_order_id'),
            trade['exit_reason'],
            trade['quantity'],
            trade.get('hold_days'),
            trade['pnl'],
            trade['pnl_pct'],
            trade.get('commission', 0),
            trade.get('signal_id'),
            trade.get('position_id'),
            trade.get('notes')
        )
        result = self._execute(query, params, fetch=True)
        return result[0]['id'] if result else None
    
    def get_trades(self, days: int = None) -> List[Dict]:
        """Get trades, optionally filtered by days"""
        query = "SELECT * FROM live_trades WHERE 1=1"
        params = []
        
        if days:
            query += " AND exit_date >= NOW() - INTERVAL '%s days'"
            params.append(days)
        
        query += " ORDER BY exit_date DESC"
        return self._execute(query, tuple(params), fetch=True)
    
    def get_trade_statistics(self, days: int = None) -> Dict:
        """Get trade statistics"""
        query = """
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                COUNT(CASE WHEN pnl <= 0 THEN 1 END) as losing_trades,
                ROUND(100.0 * COUNT(CASE WHEN pnl > 0 THEN 1 END) / NULLIF(COUNT(*), 0), 2) as win_rate,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                AVG(CASE WHEN pnl <= 0 THEN pnl END) as avg_loss,
                AVG(hold_days) as avg_hold_days
            FROM live_trades
            WHERE 1=1
        """
        params = []
        
        if days:
            query += " AND exit_date >= NOW() - INTERVAL '%s days'"
            params.append(days)
        
        result = self._execute(query, tuple(params), fetch=True)
        return dict(result[0]) if result else {}
    
    # Risk Events
    def save_risk_event(self, severity: str, event_type: str, message: str, data: Dict = None):
        """Save risk event"""
        query = """
            INSERT INTO risk_events 
            (timestamp, severity, event_type, message, data)
            VALUES (%s, %s, %s, %s, %s)
        """
        params = (
            datetime.now(),
            severity,
            event_type,
            message,
            json.dumps(data or {})
        )
        self._execute(query, params)
    
    def get_risk_events(self, severity: str = None, limit: int = 100) -> List[Dict]:
        """Get risk events"""
        query = "SELECT * FROM risk_events WHERE 1=1"
        params = []
        
        if severity:
            query += " AND severity = %s"
            params.append(severity)
        
        query += f" ORDER BY timestamp DESC LIMIT {limit}"
        return self._execute(query, tuple(params), fetch=True)
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
