"""Earnings calendar filter to avoid trading into earnings."""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from loguru import logger

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available - earnings filtering will be limited")


class EarningsCalendarFilter:
    """Filter trades based on upcoming earnings announcements."""
    
    # Safety margins
    DAYS_BEFORE_EARNINGS = 5  # Don't enter within 5 days of earnings
    DAYS_AFTER_EARNINGS = 1  # Wait 1 day after earnings
    
    def __init__(self):
        self.earnings_cache = {}
        self.cache_expiry = {}
    
    def get_next_earnings_date(
        self,
        ticker: str,
        use_cache: bool = True
    ) -> Optional[datetime]:
        """
        Get next earnings date for ticker.
        
        Args:
            ticker: Stock ticker
            use_cache: Use cached data if available
            
        Returns:
            Next earnings date or None if unknown
        """
        # Check cache
        if use_cache and ticker in self.earnings_cache:
            cache_time = self.cache_expiry.get(ticker)
            if cache_time and datetime.now() - cache_time < timedelta(days=1):
                return self.earnings_cache.get(ticker)
        
        # Try to fetch from yfinance
        if YFINANCE_AVAILABLE:
            try:
                stock = yf.Ticker(ticker)
                calendar = stock.calendar
                
                if calendar is not None and len(calendar) > 0:
                    # yfinance returns earnings date
                    earnings_date_str = calendar.get('Earnings Date')
                    
                    if earnings_date_str is not None:
                        # Parse date
                        if isinstance(earnings_date_str, str):
                            earnings_date = pd.to_datetime(earnings_date_str)
                        else:
                            earnings_date = earnings_date_str
                        
                        # Cache result
                        self.earnings_cache[ticker] = earnings_date
                        self.cache_expiry[ticker] = datetime.now()
                        
                        logger.info(f"✓ {ticker} earnings: {earnings_date.strftime('%Y-%m-%d')}")
                        return earnings_date
                
            except Exception as e:
                logger.debug(f"Could not fetch earnings for {ticker}: {e}")
        
        # If no data available, return None
        return None
    
    def days_until_earnings(
        self,
        ticker: str,
        reference_date: datetime = None
    ) -> Optional[int]:
        """
        Calculate days until next earnings.
        
        Args:
            ticker: Stock ticker
            reference_date: Date to calculate from (default: today)
            
        Returns:
            Days until earnings or None if unknown
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        earnings_date = self.get_next_earnings_date(ticker)
        
        if earnings_date is None:
            return None
        
        # Calculate days
        delta = (earnings_date - reference_date).days
        
        return delta
    
    def is_earnings_week(
        self,
        ticker: str,
        reference_date: datetime = None
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if ticker is in earnings week.
        
        Args:
            ticker: Stock ticker
            reference_date: Date to check from
            
        Returns:
            Tuple of (is_earnings_week, days_until_earnings)
        """
        days_until = self.days_until_earnings(ticker, reference_date)
        
        if days_until is None:
            # Unknown - assume not in earnings week (conservative)
            return False, None
        
        # Check if within danger zone
        is_danger_zone = (
            -self.DAYS_AFTER_EARNINGS <= days_until <= self.DAYS_BEFORE_EARNINGS
        )
        
        return is_danger_zone, days_until
    
    def filter_earnings_stocks(
        self,
        signals: List[Dict[str, any]],
        reference_date: datetime = None
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter out stocks with upcoming earnings.
        
        Args:
            signals: List of trading signals
            reference_date: Date to filter from
            
        Returns:
            Tuple of (safe_signals, filtered_signals)
        """
        safe_signals = []
        filtered_signals = []
        
        for signal in signals:
            ticker = signal.get('ticker')
            
            if not ticker:
                continue
            
            is_danger, days_until = self.is_earnings_week(ticker, reference_date)
            
            # Add earnings info to signal
            signal['earnings_info'] = {
                'days_until_earnings': days_until,
                'is_earnings_week': is_danger
            }
            
            if is_danger:
                signal['filtered_reason'] = f"Earnings in {days_until} days"
                filtered_signals.append(signal)
                logger.info(f"✗ {ticker} filtered: earnings in {days_until} days")
            else:
                safe_signals.append(signal)
        
        logger.info(
            f"Earnings filter: {len(safe_signals)} safe, {len(filtered_signals)} filtered"
        )
        
        return safe_signals, filtered_signals
    
    def check_holding_through_earnings(
        self,
        ticker: str,
        entry_date: datetime,
        expected_hold_days: int = 5
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if holding period would cross earnings.
        
        Args:
            ticker: Stock ticker
            entry_date: Entry date for position
            expected_hold_days: Expected holding period
            
        Returns:
            Tuple of (would_cross_earnings, days_to_earnings_from_entry)
        """
        earnings_date = self.get_next_earnings_date(ticker)
        
        if earnings_date is None:
            # Unknown - assume safe (but log warning)
            return False, None
        
        exit_date = entry_date + timedelta(days=expected_hold_days)
        
        # Check if earnings falls within holding period
        would_cross = entry_date <= earnings_date <= exit_date
        
        days_from_entry = (earnings_date - entry_date).days
        
        return would_cross, days_from_entry
    
    def get_safe_hold_days(
        self,
        ticker: str,
        entry_date: datetime = None
    ) -> Optional[int]:
        """
        Calculate maximum safe holding period before earnings.
        
        Args:
            ticker: Stock ticker
            entry_date: Entry date (default: today)
            
        Returns:
            Max safe holding days or None if unknown
        """
        if entry_date is None:
            entry_date = datetime.now()
        
        days_until = self.days_until_earnings(ticker, entry_date)
        
        if days_until is None:
            return None
        
        # Safe to hold until DAYS_BEFORE_EARNINGS days before earnings
        safe_days = days_until - self.DAYS_BEFORE_EARNINGS
        
        return max(0, safe_days)
    
    def bulk_update_earnings_cache(
        self,
        tickers: List[str]
    ) -> Dict[str, Optional[datetime]]:
        """
        Update earnings cache for multiple tickers.
        
        Args:
            tickers: List of tickers to update
            
        Returns:
            Dictionary of ticker -> earnings_date
        """
        logger.info(f"Updating earnings calendar for {len(tickers)} tickers...")
        
        results = {}
        for ticker in tickers:
            earnings_date = self.get_next_earnings_date(ticker, use_cache=False)
            results[ticker] = earnings_date
        
        logger.info(f"✓ Updated {len(results)} earnings dates")
        
        return results


# Global instance
earnings_filter = EarningsCalendarFilter()
