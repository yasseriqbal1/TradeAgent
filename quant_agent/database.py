"""Database connection and operations."""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import settings


class Database:
    """PostgreSQL database manager."""
    
    def __init__(self):
        self.connection_params = {
            "host": settings.db_host,
            "port": settings.db_port,
            "database": settings.db_name,
            "user": settings.db_user,
            "password": settings.db_password
        }
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def create_scan_run(self, scan_type: str, status: str, top_n: int, 
                        stocks_scanned: int, error_message: Optional[str] = None,
                        execution_time: Optional[float] = None) -> int:
        """Create a new scan run record."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO scan_runs (scan_type, status, top_n, stocks_scanned, 
                                          error_message, execution_time_seconds)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (scan_type, status, top_n, stocks_scanned, error_message, execution_time))
                return cur.fetchone()[0]
    
    def save_signals(self, scan_run_id: int, signals: List[Dict[str, Any]]) -> List[int]:
        """Save signal records for a scan run."""
        signal_ids = []
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for signal in signals:
                    cur.execute("""
                        INSERT INTO signals (scan_run_id, ticker, rank, composite_score,
                                            price, volume, market_cap, sector, selected)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        scan_run_id,
                        signal["ticker"],
                        signal["rank"],
                        signal["composite_score"],
                        signal.get("price"),
                        signal.get("volume"),
                        signal.get("market_cap"),
                        signal.get("sector"),
                        signal.get("selected", True)
                    ))
                    signal_ids.append(cur.fetchone()[0])
        return signal_ids
    
    def save_factors(self, signal_id: int, factors: Dict[str, Any]):
        """Save factor values for a signal."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO factors (
                        signal_id, return_5d, return_10d, return_20d,
                        rsi_14, ema_9, ema_21, ema_50,
                        volatility_20d, atr_14, volume_20d_avg, volume_ratio,
                        z_momentum, z_volatility, z_volume
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    signal_id,
                    factors.get("return_5d"),
                    factors.get("return_10d"),
                    factors.get("return_20d"),
                    factors.get("rsi_14"),
                    factors.get("ema_9"),
                    factors.get("ema_21"),
                    factors.get("ema_50"),
                    factors.get("volatility_20d"),
                    factors.get("atr_14"),
                    factors.get("volume_20d_avg"),
                    factors.get("volume_ratio"),
                    factors.get("z_momentum"),
                    factors.get("z_volatility"),
                    factors.get("z_volume")
                ))
    
    def get_latest_premarket_signals(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the latest premarket scan signals."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT s.ticker, s.rank, s.composite_score, s.price, s.volume,
                           sr.run_timestamp
                    FROM signals s
                    JOIN scan_runs sr ON s.scan_run_id = sr.id
                    WHERE sr.scan_type = 'premarket' 
                      AND sr.status = 'success'
                      AND s.selected = true
                    ORDER BY sr.run_timestamp DESC, s.rank
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cur.fetchall()]
    
    def get_scan_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scan run history."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, scan_type, run_timestamp, status, top_n, 
                           stocks_scanned, execution_time_seconds
                    FROM scan_runs
                    ORDER BY run_timestamp DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cur.fetchall()]


# Global database instance
db = Database()
