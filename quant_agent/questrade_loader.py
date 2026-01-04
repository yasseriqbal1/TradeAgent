"""Questrade API data loader - secure alternative to yfinance."""

import os
import requests
import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv

from .config import DATA_DIR


class QuestradeAPI:
    """Handles Questrade API authentication and data fetching."""
    
    def __init__(self, refresh_token: Optional[str] = None, server_type: str = "practice"):
        """
        Initialize Questrade API client.
        
        Args:
            refresh_token: OAuth refresh token (loaded from .env if not provided)
            server_type: 'practice' or 'live'
        """
        # Load from .env file if not provided
        if refresh_token is None:
            load_dotenv()
            refresh_token = os.getenv("QUESTRADE_REFRESH_TOKEN")
            server_type = os.getenv("QUESTRADE_SERVER_TYPE", "practice")
        
        if not refresh_token:
            raise ValueError(
                "Questrade refresh token not found. "
                "Create .env file from .env.template and add your token."
            )
        
        self.refresh_token = refresh_token
        self.server_type = server_type
        self.api_server = None
        self.access_token = None
        self.token_expiry = None
        
        # Find .env file path for token persistence
        self.env_path = Path.cwd() / '.env'
        if not self.env_path.exists():
            # Try parent directories
            for parent in Path.cwd().parents:
                env_file = parent / '.env'
                if env_file.exists():
                    self.env_path = env_file
                    break
        
        # Authenticate on initialization
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate and get access token."""
        # The token endpoint URL - always use login.questrade.com
        # (practice tokens work with the same endpoint)
        token_url = "https://login.questrade.com/oauth2/token"
        
        try:
            logger.info(f"Authenticating with Questrade API...")
            
            # Build the full URL exactly as the browser does
            full_url = f"{token_url}?grant_type=refresh_token&refresh_token={self.refresh_token}"
            
            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
            
            # Make the request
            response = requests.get(full_url, headers=headers, timeout=10)
            
            # Log the status for debugging
            logger.debug(f"Response status: {response.status_code}")
            
            # If not successful, log the response (without exposing token)
            if response.status_code != 200:
                logger.error(f"Authentication failed with status {response.status_code}")
                logger.error(f"Response: {response.text[:100]}")  # Only first 100 chars
            
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            self.api_server = data["api_server"]
            new_refresh_token = data["refresh_token"]  # Questrade provides new token
            
            # Save new refresh token to .env file for persistence
            if new_refresh_token != self.refresh_token:
                self._save_refresh_token(new_refresh_token)
                self.refresh_token = new_refresh_token
            
            # Token expires in seconds (typically 1800 = 30 minutes)
            expires_in = data.get("expires_in", 1800)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            
            logger.info(f"✓ Authenticated successfully. API server: {self.api_server}")
            logger.debug(f"Access token expires in {expires_in} seconds")
            
        except Exception as e:
            logger.error(f"Questrade authentication failed: {e}")
            raise
    
    def _save_refresh_token(self, new_token: str):
        """Save new refresh token to .env file."""
        try:
            if not self.env_path.exists():
                logger.warning(f".env file not found at {self.env_path}, cannot persist token")
                return
            
            # Read current .env content
            with open(self.env_path, 'r') as f:
                lines = f.readlines()
            
            # Update the refresh token line
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('QUESTRADE_REFRESH_TOKEN='):
                    lines[i] = f'QUESTRADE_REFRESH_TOKEN={new_token}\n'
                    updated = True
                    break
            
            # Write back to .env
            if updated:
                with open(self.env_path, 'w') as f:
                    f.writelines(lines)
                logger.debug("✓ Refresh token updated in .env file")
            else:
                logger.warning("Could not find QUESTRADE_REFRESH_TOKEN in .env file")
                
        except Exception as e:
            logger.warning(f"Failed to save refresh token to .env: {e}")
    
    def _ensure_authenticated(self):
        """Check token expiry and re-authenticate if needed."""
        if not self.token_expiry or datetime.now() >= self.token_expiry:
            logger.info("Access token expired, re-authenticating...")
            self._authenticate()
    
    def _request(self, endpoint: str, params: Optional[Dict] = None):
        """Make authenticated API request with retry on 401."""
        self._ensure_authenticated()
        
        # Remove leading slash from endpoint if api_server already ends with /
        api_server = self.api_server.rstrip('/')
        endpoint = endpoint if not endpoint.startswith('/') else endpoint[1:]
        url = f"{api_server}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers, params=params or {})
            
            # If 401 Unauthorized, token expired - re-authenticate and retry once
            if response.status_code == 401:
                logger.warning("Received 401 Unauthorized, re-authenticating...")
                self._authenticate()
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = requests.get(url, headers=headers, params=params or {})
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"API request failed: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise
    
    def search_symbols(self, ticker: str) -> Optional[int]:
        """
        Search for symbol ID by ticker.
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL')
        
        Returns:
            Symbol ID or None if not found
        """
        try:
            data = self._request("/v1/symbols/search", {"prefix": ticker})
            symbols = data.get("symbols", [])
            
            # Find exact match for ticker
            for symbol in symbols:
                if symbol.get("symbol") == ticker:
                    symbol_id = symbol.get("symbolId")
                    logger.debug(f"{ticker} -> symbolId: {symbol_id}")
                    return symbol_id
            
            logger.warning(f"Symbol not found: {ticker}")
            return None
            
        except Exception as e:
            logger.error(f"Symbol search failed for {ticker}: {e}")
            return None
    
    def get_quotes(self, symbol_ids: List[int]) -> List[Dict]:
        """
        Get real-time quotes for multiple symbols.
        
        Args:
            symbol_ids: List of symbol IDs
        
        Returns:
            List of quote dictionaries with price/volume data
        """
        try:
            # Questrade API accepts comma-separated symbol IDs
            ids_str = ",".join(str(sid) for sid in symbol_ids)
            data = self._request("/v1/markets/quotes", {"ids": ids_str})
            quotes = data.get("quotes", [])
            
            logger.debug(f"Retrieved {len(quotes)} quotes for {len(symbol_ids)} symbols")
            return quotes
            
        except Exception as e:
            logger.error(f"Failed to get quotes: {e}")
            return []
    
    def get_accounts(self) -> List[Dict]:
        """
        Get list of accounts for the user.
        
        Returns:
            List of account dictionaries with account numbers and types
        """
        try:
            data = self._request("/v1/accounts")
            accounts = data.get("accounts", [])
            logger.debug(f"Retrieved {len(accounts)} accounts")
            return accounts
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return []
    
    def get_balances(self, account_number: str) -> Dict:
        """
        Get account balances including cash and buying power.
        
        Args:
            account_number: Account number
        
        Returns:
            Dictionary with balance information:
            - cash: Total cash balance
            - marketValue: Current market value of positions
            - totalEquity: Total account equity
            - buyingPower: Available buying power
        """
        try:
            data = self._request(f"/v1/accounts/{account_number}/balances")
            balances = data.get("combinedBalances", [{}])[0]
            logger.debug(f"Retrieved balances: Cash=${balances.get('cash', 0):.2f}, Equity=${balances.get('totalEquity', 0):.2f}")
            return balances
        except Exception as e:
            logger.error(f"Failed to get balances: {e}")
            return {}
    
    def get_positions(self, account_number: str) -> List[Dict]:
        """
        Get current positions in the account.
        
        Args:
            account_number: Account number
        
        Returns:
            List of position dictionaries with symbol, quantity, price info
        """
        try:
            data = self._request(f"/v1/accounts/{account_number}/positions")
            positions = data.get("positions", [])
            logger.debug(f"Retrieved {len(positions)} positions")
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_candles(self, symbol_id: int, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Get historical OHLC candle data.
        
        Args:
            symbol_id: Questrade symbol ID
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame with OHLC data
        """
        try:
            # Format dates as ISO strings
            start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S-05:00")
            end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S-05:00")
            
            data = self._request(
                f"/v1/markets/candles/{symbol_id}",
                {
                    "startTime": start_str,
                    "endTime": end_str,
                    "interval": "OneDay"
                }
            )
            
            candles = data.get("candles", [])
            
            if not candles:
                logger.warning(f"No candles returned for symbolId {symbol_id}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            # Rename columns to match yfinance format
            df = df.rename(columns={
                "start": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            })
            
            # Parse date and set as index (force timezone-naive)
            df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)
            df = df.set_index("Date")
            
            # Select only OHLCV columns
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            
            logger.debug(f"Retrieved {len(df)} candles for symbolId {symbol_id}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get candles for symbolId {symbol_id}: {e}")
            return pd.DataFrame()


class QuestradeDataLoader:
    """Drop-in replacement for yfinance DataLoader using Questrade API."""
    
    def __init__(self, cache_dir: Path = DATA_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.api = QuestradeAPI()
        self._symbol_cache = {}  # ticker -> symbolId mapping
    
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
            period: Data period (e.g., '60d', '90d')
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
        
        # Get symbol ID
        if ticker not in self._symbol_cache:
            symbol_id = self.api.search_symbols(ticker)
            if symbol_id is None:
                logger.error(f"Could not find symbol ID for {ticker}")
                return None
            self._symbol_cache[ticker] = symbol_id
        
        symbol_id = self._symbol_cache[ticker]
        
        # Parse period (e.g., "60d" -> 60 days)
        days = int(period.replace("d", ""))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Download data
        for attempt in range(max_retries):
            try:
                logger.debug(f"Downloading {ticker} from Questrade (attempt {attempt + 1}/{max_retries})")
                
                df = self.api.get_candles(symbol_id, start_date, end_date)
                
                if df.empty:
                    logger.warning(f"{ticker}: No data returned (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        continue
                    return None
                
                # Save to cache
                df.to_csv(cache_path)
                logger.info(f"✓ Downloaded and cached {ticker} ({len(df)} days)")
                return df
                
            except Exception as e:
                logger.error(f"Failed to download {ticker}: {e}")
                if attempt < max_retries - 1:
                    continue
                return None
        
        return None
    
    def download_universe(self, tickers: List[str], period: str = "60d",
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
        
        logger.info(f"Downloading data for {len(tickers)} tickers from Questrade")
        
        for ticker in tickers:
            df = self.download_ticker(ticker, period, use_cache)
            if df is not None and not df.empty and len(df) >= 15:  # Minimum 15 trading days
                data[ticker] = df
            else:
                failed.append(ticker)
        
        logger.info(f"Successfully loaded {len(data)} tickers, {len(failed)} failed")
        if failed:
            logger.warning(f"Failed tickers: {', '.join(failed)}")
        
        return data
