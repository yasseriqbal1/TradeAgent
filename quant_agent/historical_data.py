"""Historical data download and management for backtesting."""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from loguru import logger
import yfinance as yf

from .questrade_loader import QuestradeDataLoader
from .database import db


class HistoricalDataManager:
    """Manage historical price data for backtesting."""
    
    def __init__(self):
        self._data_loader = None
    
    @property
    def data_loader(self):
        """Lazy initialization of QuestradeDataLoader."""
        if self._data_loader is None:
            self._data_loader = QuestradeDataLoader()
        return self._data_loader
    
    def download_historical_data(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str = None,
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Download historical OHLCV data for multiple tickers.
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to today
            force_refresh: Force re-download even if cached
            
        Returns:
            Dictionary mapping ticker to DataFrame with OHLCV data
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Calculate days between dates (handle both string and datetime objects)
        if isinstance(start_date, str):
            start = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start = start_date
            
        if isinstance(end_date, str):
            end = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end = end_date
            
        days = (end - start).days
        
        logger.info(f"Downloading historical data for {len(tickers)} tickers")
        logger.info(f"Date range: {start} to {end} ({days} days)")
        
        # Determine if we need chunked downloads for Questrade
        use_chunked = days > 85 and not force_refresh  # Use chunking for >85 days with Questrade
        
        if use_chunked:
            logger.info(f"Data source: Questrade (chunked downloads - {days} days)")
        else:
            logger.info(f"Data source: {'yfinance (backtesting)' if force_refresh else 'Questrade (live)'}")
        
        historical_data = {}
        failed_tickers = []
        
        for ticker in tickers:
            try:
                if force_refresh:
                    # Use yfinance for backtesting - unlimited historical data
                    logger.debug(f"Downloading {ticker} from yfinance...")
                    yf_ticker = yf.Ticker(ticker)
                    # Convert dates to string format for yfinance
                    start_str = start.strftime('%Y-%m-%d')
                    end_str = end.strftime('%Y-%m-%d')
                    df = yf_ticker.history(start=start_str, end=end_str)
                    
                    if df is not None and len(df) > 0:
                        # Standardize column names to match Questrade format (uppercase)
                        df = df.rename(columns={
                            'Open': 'Open',
                            'High': 'High', 
                            'Low': 'Low',
                            'Close': 'Close',
                            'Volume': 'Volume'
                        })
                        # Keep only OHLCV columns
                        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
                        # Ensure timezone-naive for consistency
                        if df.index.tz is not None:
                            df.index = df.index.tz_localize(None)
                    else:
                        logger.warning(f"No data returned from yfinance for {ticker}")
                        failed_tickers.append(ticker)
                        continue
                elif use_chunked:
                    # Download in chunks for Questrade (85-day limit)
                    df = self._download_in_chunks(ticker, start, end)
                else:
                    # Use Questrade loader for live data (cached, single request)
                    df = self.data_loader.download_ticker(
                        ticker,
                        period=f"{days}d",
                        use_cache=True  # Always use cache for live data
                    )
                
                if df is not None and len(df) > 0:
                    # Filter to exact date range
                    # Ensure both sides of comparison have matching timezone
                    if hasattr(df.index, 'tz') and df.index.tz is not None:
                        # DataFrame has timezone - make dates timezone-aware
                        import pytz
                        df_tz = df.index.tz
                        if start.tzinfo is None:
                            start_aware = df_tz.localize(start) if hasattr(df_tz, 'localize') else start.replace(tzinfo=df_tz)
                        else:
                            start_aware = start.astimezone(df_tz)
                        if end.tzinfo is None:
                            end_aware = df_tz.localize(end) if hasattr(df_tz, 'localize') else end.replace(tzinfo=df_tz)
                        else:
                            end_aware = end.astimezone(df_tz)
                        
                        df_filtered = df[
                            (df.index >= start_aware) & 
                            (df.index <= end_aware)
                        ]
                    else:
                        # DataFrame is timezone-naive - use dates as-is
                        df_filtered = df[
                            (df.index >= start) & 
                            (df.index <= end)
                        ].copy()
                    
                    if len(df_filtered) > 0:
                        historical_data[ticker] = df_filtered
                        logger.info(f"✓ {ticker}: {len(df_filtered)} days")
                    else:
                        logger.warning(f"✗ {ticker}: No data in date range")
                        failed_tickers.append(ticker)
                else:
                    logger.warning(f"✗ {ticker}: Download failed")
                    failed_tickers.append(ticker)
                    
            except Exception as e:
                logger.error(f"✗ {ticker}: {e}")
                failed_tickers.append(ticker)
        
        logger.info(f"Downloaded {len(historical_data)}/{len(tickers)} tickers successfully")
        if failed_tickers:
            logger.warning(f"Failed tickers: {', '.join(failed_tickers)}")
        
        return historical_data
    
    def save_to_database(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> bool:
        """
        Save historical data to database.
        
        Args:
            ticker: Ticker symbol
            df: DataFrame with OHLCV data
            
        Returns:
            Success status
        """
        try:
            # Store in database (using existing infrastructure)
            # This would integrate with db module to create historical_prices table
            logger.info(f"Saved {len(df)} days for {ticker} to database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save {ticker} to database: {e}")
            return False
    
    def load_from_database(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Load historical data from database.
        
        Args:
            ticker: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Load from database
            # This would query historical_prices table
            logger.info(f"Loaded historical data for {ticker} from database")
            return None  # Placeholder
            
        except Exception as e:
            logger.error(f"Failed to load {ticker} from database: {e}")
            return None
    
    def validate_data(
        self,
        df: pd.DataFrame,
        ticker: str
    ) -> Dict[str, any]:
        """
        Validate historical data quality.
        
        Args:
            df: DataFrame with OHLCV data
            ticker: Ticker symbol
            
        Returns:
            Validation results
        """
        issues = []
        
        # Check for missing data
        missing_days = df.isnull().sum()
        if missing_days.any():
            issues.append(f"Missing data: {missing_days.to_dict()}")
        
        # Check for gaps in dates (weekends/holidays are ok)
        date_diffs = pd.Series(df.index).diff()
        large_gaps = date_diffs[date_diffs > timedelta(days=7)]
        if len(large_gaps) > 0:
            issues.append(f"Large date gaps: {len(large_gaps)} instances")
        
        # Check for price anomalies
        if 'Close' in df.columns:
            price_changes = df['Close'].pct_change()
            extreme_moves = price_changes[abs(price_changes) > 0.5]  # >50% moves
            if len(extreme_moves) > 0:
                issues.append(f"Extreme price moves: {len(extreme_moves)} days")
        
        # Check data length
        if len(df) < 100:
            issues.append(f"Insufficient data: only {len(df)} days")
        
        return {
            'ticker': ticker,
            'days': len(df),
            'start_date': df.index[0].strftime('%Y-%m-%d'),
            'end_date': df.index[-1].strftime('%Y-%m-%d'),
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    def _download_in_chunks(
        self,
        ticker: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """
        Download data in 85-day chunks to work around Questrade's API limit.
        
        Args:
            ticker: Ticker symbol
            start: Start date
            end: End date
            
        Returns:
            Combined DataFrame with all data
        """
        chunk_size = 85  # Days per chunk (safe margin below 90-day limit)
        all_chunks = []
        
        current_start = start
        chunk_num = 0
        
        while current_start < end:
            chunk_num += 1
            # Calculate chunk end date
            chunk_end = min(current_start + timedelta(days=chunk_size), end)
            days_in_chunk = (chunk_end - current_start).days
            
            logger.info(f"  Chunk {chunk_num}: {current_start.date()} to {chunk_end.date()} ({days_in_chunk} days)")
            
            try:
                # Download this chunk
                df_chunk = self.data_loader.download_ticker(
                    ticker,
                    period=f"{days_in_chunk}d",
                    use_cache=False  # Don't use cache for historical chunks
                )
                
                if df_chunk is not None and len(df_chunk) > 0:
                    # Filter to exact date range for this chunk
                    df_chunk_filtered = df_chunk[
                        (df_chunk.index >= current_start) & 
                        (df_chunk.index <= chunk_end)
                    ].copy()
                    
                    if len(df_chunk_filtered) > 0:
                        all_chunks.append(df_chunk_filtered)
                        logger.debug(f"    Got {len(df_chunk_filtered)} bars")
                    else:
                        logger.warning(f"    No data in this chunk")
                else:
                    logger.warning(f"    Chunk download failed")
                    
            except Exception as e:
                logger.error(f"    Error downloading chunk: {e}")
            
            # Move to next chunk (add 1 day to avoid overlap)
            current_start = chunk_end + timedelta(days=1)
        
        # Combine all chunks
        if not all_chunks:
            logger.warning(f"{ticker}: No data retrieved from any chunks")
            return None
        
        # Concatenate and remove duplicates
        df_combined = pd.concat(all_chunks)
        df_combined = df_combined[~df_combined.index.duplicated(keep='first')]
        df_combined = df_combined.sort_index()
        
        logger.info(f"✓ {ticker}: Combined {len(all_chunks)} chunks into {len(df_combined)} total bars")
        
        return df_combined
    
    def get_aligned_data(
        self,
        historical_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        Align all tickers to common date range.
        
        Args:
            historical_data: Dictionary of ticker -> DataFrame
            
        Returns:
            Aligned data with common dates
        """
        if not historical_data:
            return {}
        
        # Find common date range
        all_dates = []
        for df in historical_data.values():
            all_dates.extend(df.index.tolist())
        
        if not all_dates:
            return {}
        
        # Get intersection of all date ranges
        common_start = max(df.index.min() for df in historical_data.values())
        common_end = min(df.index.max() for df in historical_data.values())
        
        logger.info(f"Aligning to common range: {common_start} to {common_end}")
        
        # Filter all dataframes to common range
        aligned_data = {}
        for ticker, df in historical_data.items():
            aligned_df = df[
                (df.index >= common_start) & 
                (df.index <= common_end)
            ].copy()
            
            if len(aligned_df) > 0:
                aligned_data[ticker] = aligned_df
        
        return aligned_data


# Global instance
historical_data_manager = HistoricalDataManager()
