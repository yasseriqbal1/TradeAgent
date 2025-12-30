"""Data loading and caching from yfinance."""

import yfinance as yf
import pandas as pd
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta
from loguru import logger
import time

from .config import DATA_DIR, scan_config


class DataLoader:
    """Handles market data fetching and caching."""
    
    def __init__(self, cache_dir: Path = DATA_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_path(self, ticker: str) -> Path:
        """Get cache file path for a ticker."""
        return self.cache_dir / f"{ticker}.csv"
    
    def _is_cache_fresh(self, cache_path: Path, max_age_hours: int = 24) -> bool:
        """Check if cached data is fresh enough."""
        if not cache_path.exists():
            return False
        
        file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - file_time
        return age < timedelta(hours=max_age_hours)
    
    def download_ticker(self, ticker: str, period: str = "60d", 
                       use_cache: bool = True, max_retries: int = 3) -> Optional[pd.DataFrame]:
        """
        Download historical data for a single ticker.
        
        Args:
            ticker: Stock ticker symbol
            period: Data period (e.g., '60d', '1y')
            use_cache: Whether to use cached data
            max_retries: Number of retry attempts
        
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        cache_path = self._get_cache_path(ticker)
        
        # Try cache first
        if use_cache and self._is_cache_fresh(cache_path, max_age_hours=6):
            try:
                df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
                logger.debug(f"Loaded {ticker} from cache")
                return df
            except Exception as e:
                logger.warning(f"Cache read failed for {ticker}: {e}")
        
        # Download fresh data with retries
        for attempt in range(max_retries):
            try:
                logger.debug(f"Downloading {ticker} (attempt {attempt + 1}/{max_retries})")
                
                # Add delay between requests to avoid rate limiting
                if attempt > 0:
                    time.sleep(2)
                
                # Use explicit date range instead of period for better reliability
                end_date = datetime.now()
                start_date = end_date - timedelta(days=90)  # Use 90 days to ensure we get enough data
                
                logger.debug(f"{ticker}: Requesting data from {start_date.date()} to {end_date.date()}")
                
                # Try using yfinance.download with explicit dates
                df = yf.download(
                    ticker, 
                    start=start_date,
                    end=end_date,
                    progress=False,
                    show_errors=False
                )
                
                logger.debug(f"{ticker}: Received {len(df) if not df.empty else 0} rows")
                
                if df.empty:
                    logger.warning(f"{ticker}: No data returned (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return None
                
                # Save to cache
                df.to_csv(cache_path)
                logger.debug(f"Downloaded and cached {ticker}")
                return df
                
            except Exception as e:
                logger.error(f"Failed to get ticker '{ticker}' reason: {e}")
                logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    logger.error(f"Failed to download {ticker} after {max_retries} attempts")
                    return None
        
        return None
    
    def download_universe(self, tickers: List[str], period: str = "30d",
                         use_cache: bool = True) -> dict:
        """
        Download data for multiple tickers.
        
        Args:
            tickers: List of ticker symbols
            period: Data period
            use_cache: Whether to use cached data
        
        Returns:
            Dictionary mapping ticker to DataFrame
        """
        data = {}
        failed = []
        
        logger.info(f"Downloading data for {len(tickers)} tickers")
        
        for ticker in tickers:
            df = self.download_ticker(ticker, period, use_cache)
            if df is not None and not df.empty and len(df) >= 30:
                # Basic validation: need at least 30 days
                data[ticker] = df
            else:
                failed.append(ticker)
        
        logger.info(f"Successfully loaded {len(data)} tickers, {len(failed)} failed")
        if failed:
            logger.debug(f"Failed tickers: {', '.join(failed[:10])}")
        
        return data
    
    def get_latest_price(self, ticker: str) -> Optional[float]:
        """Get the most recent closing price for a ticker."""
        df = self.download_ticker(ticker, period="5d", use_cache=False)
        if df is not None and not df.empty:
            return float(df['Close'].iloc[-1])
        return None
    
    def get_ticker_info(self, ticker: str) -> dict:
        """Get ticker information (sector, market cap, etc.)."""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                "sector": info.get("sector", "Unknown"),
                "market_cap": info.get("marketCap"),
                "name": info.get("longName", ticker)
            }
        except Exception as e:
            logger.warning(f"Failed to get info for {ticker}: {e}")
            return {"sector": "Unknown", "market_cap": None, "name": ticker}
    
    def clear_cache(self, older_than_days: int = 7):
        """Clear old cache files."""
        cutoff = datetime.now() - timedelta(days=older_than_days)
        removed = 0
        
        for cache_file in self.cache_dir.glob("*.csv"):
            file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if file_time < cutoff:
                cache_file.unlink()
                removed += 1
        
        if removed > 0:
            logger.info(f"Cleared {removed} old cache files")


# Global data loader instance
data_loader = DataLoader()
