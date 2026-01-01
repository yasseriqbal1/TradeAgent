"""
Real-Time Market Data Handler
Manages WebSocket connections for streaming quotes and market data
"""

import logging
import time
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import pytz

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    """Real-time quote data"""
    ticker: str
    last_price: float
    bid_price: float
    ask_price: float
    bid_size: int
    ask_size: int
    volume: int
    timestamp: datetime
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        return self.ask_price - self.bid_price
    
    @property
    def mid_price(self) -> float:
        """Calculate mid-point price"""
        return (self.bid_price + self.ask_price) / 2.0


class RealtimeDataHandler:
    """
    Handles real-time market data streaming
    
    Features:
    - Quote subscriptions
    - Market hours detection
    - Connection management
    - Data validation
    """
    
    def __init__(self, data_loader, timezone: str = 'America/New_York'):
        """
        Initialize real-time data handler
        
        Args:
            data_loader: QuestradeDataLoader instance for API access
            timezone: Market timezone (default: EST)
        """
        self.data_loader = data_loader
        self.timezone = pytz.timezone(timezone)
        
        # Quote storage
        self._quotes: Dict[str, Quote] = {}
        self._subscribed_tickers: List[str] = []
        
        # Connection state
        self._connected = False
        self._last_update: Dict[str, datetime] = {}
        
        # Callbacks for quote updates
        self._quote_callbacks: List[Callable] = []
        
        logger.info("RealtimeDataHandler initialized")
    
    def connect(self) -> bool:
        """
        Establish connection to data source
        
        Returns:
            bool: True if connected successfully
        """
        try:
            # For Questrade, we'll use periodic polling instead of WebSocket
            # since Questrade doesn't provide WebSocket streaming
            self._connected = True
            logger.info("Connected to data source (polling mode)")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from data source"""
        self._connected = False
        self._subscribed_tickers.clear()
        self._quotes.clear()
        logger.info("Disconnected from data source")
    
    def subscribe_quotes(self, tickers: List[str]) -> bool:
        """
        Subscribe to real-time quotes for tickers
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            bool: True if subscription successful
        """
        if not self._connected:
            logger.warning("Not connected. Call connect() first")
            return False
        
        try:
            for ticker in tickers:
                if ticker not in self._subscribed_tickers:
                    self._subscribed_tickers.append(ticker)
                    logger.info(f"Subscribed to {ticker}")
            
            # Initial fetch of quotes
            self.refresh_quotes()
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to quotes: {e}")
            return False
    
    def unsubscribe_quotes(self, tickers: List[str]):
        """
        Unsubscribe from real-time quotes
        
        Args:
            tickers: List of ticker symbols to unsubscribe
        """
        for ticker in tickers:
            if ticker in self._subscribed_tickers:
                self._subscribed_tickers.remove(ticker)
                if ticker in self._quotes:
                    del self._quotes[ticker]
                logger.info(f"Unsubscribed from {ticker}")
    
    def refresh_quotes(self, tickers: Optional[List[str]] = None) -> bool:
        """
        Refresh quotes for subscribed tickers
        
        Args:
            tickers: Specific tickers to refresh (None = all subscribed)
            
        Returns:
            bool: True if refresh successful
        """
        if not self._connected:
            return False
        
        tickers_to_refresh = tickers or self._subscribed_tickers
        
        if not tickers_to_refresh:
            return True
        
        try:
            # Fetch current quotes from Questrade
            for ticker in tickers_to_refresh:
                try:
                    # Use the data loader to get latest quote
                    # For now, we'll use the last bar from a 1-day download
                    df = self.data_loader.download_ticker(ticker, period='1d', use_cache=False)
                    
                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        
                        quote = Quote(
                            ticker=ticker,
                            last_price=float(latest['Close']),
                            bid_price=float(latest['Close'] * 0.999),  # Approximate
                            ask_price=float(latest['Close'] * 1.001),  # Approximate
                            bid_size=100,
                            ask_size=100,
                            volume=int(latest['Volume']),
                            timestamp=latest.name.to_pydatetime()
                        )
                        
                        self._quotes[ticker] = quote
                        self._last_update[ticker] = datetime.now(self.timezone)
                        
                        # Trigger callbacks
                        self._trigger_quote_callbacks(quote)
                        
                        logger.debug(f"Refreshed quote for {ticker}: ${quote.last_price:.2f}")
                    else:
                        logger.warning(f"No data returned for {ticker}")
                        
                except Exception as e:
                    logger.error(f"Failed to refresh quote for {ticker}: {e}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh quotes: {e}")
            return False
    
    def get_quote(self, ticker: str) -> Optional[Quote]:
        """
        Get latest quote for a ticker
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Quote object or None if not available
        """
        return self._quotes.get(ticker)
    
    def get_all_quotes(self) -> Dict[str, Quote]:
        """
        Get all current quotes
        
        Returns:
            Dictionary of ticker -> Quote
        """
        return self._quotes.copy()
    
    def get_last_price(self, ticker: str) -> Optional[float]:
        """
        Get last traded price for a ticker
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Last price or None
        """
        quote = self.get_quote(ticker)
        return quote.last_price if quote else None
    
    def is_market_open(self) -> bool:
        """
        Check if market is currently open
        
        Returns:
            bool: True if market is open
        """
        now = datetime.now(self.timezone)
        
        # Check if it's a weekday (0 = Monday, 4 = Friday)
        if now.weekday() >= 5:
            return False
        
        # Market hours: 9:30 AM - 4:00 PM EST
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        
        current_time = now.time()
        return market_open <= current_time <= market_close
    
    def is_premarket_hours(self) -> bool:
        """
        Check if currently in pre-market hours
        
        Returns:
            bool: True if in pre-market (4:00 AM - 9:30 AM EST)
        """
        now = datetime.now(self.timezone)
        
        # Check if it's a weekday
        if now.weekday() >= 5:
            return False
        
        premarket_open = dt_time(4, 0)
        market_open = dt_time(9, 30)
        
        current_time = now.time()
        return premarket_open <= current_time < market_open
    
    def is_afterhours(self) -> bool:
        """
        Check if currently in after-hours trading
        
        Returns:
            bool: True if after-hours (4:00 PM - 8:00 PM EST)
        """
        now = datetime.now(self.timezone)
        
        # Check if it's a weekday
        if now.weekday() >= 5:
            return False
        
        market_close = dt_time(16, 0)
        afterhours_close = dt_time(20, 0)
        
        current_time = now.time()
        return market_close < current_time <= afterhours_close
    
    def get_market_status(self) -> str:
        """
        Get current market status
        
        Returns:
            str: 'open', 'premarket', 'afterhours', or 'closed'
        """
        if self.is_market_open():
            return 'open'
        elif self.is_premarket_hours():
            return 'premarket'
        elif self.is_afterhours():
            return 'afterhours'
        else:
            return 'closed'
    
    def register_quote_callback(self, callback: Callable[[Quote], None]):
        """
        Register a callback to be called on quote updates
        
        Args:
            callback: Function that takes a Quote object
        """
        if callback not in self._quote_callbacks:
            self._quote_callbacks.append(callback)
            logger.info(f"Registered quote callback: {callback.__name__}")
    
    def unregister_quote_callback(self, callback: Callable):
        """
        Unregister a quote callback
        
        Args:
            callback: Previously registered callback function
        """
        if callback in self._quote_callbacks:
            self._quote_callbacks.remove(callback)
            logger.info(f"Unregistered quote callback: {callback.__name__}")
    
    def _trigger_quote_callbacks(self, quote: Quote):
        """
        Trigger all registered callbacks with new quote
        
        Args:
            quote: Updated Quote object
        """
        for callback in self._quote_callbacks:
            try:
                callback(quote)
            except Exception as e:
                logger.error(f"Error in quote callback {callback.__name__}: {e}")
    
    def get_quote_age(self, ticker: str) -> Optional[float]:
        """
        Get age of quote in seconds
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Age in seconds or None if no quote
        """
        if ticker not in self._last_update:
            return None
        
        age = (datetime.now(self.timezone) - self._last_update[ticker]).total_seconds()
        return age
    
    def is_quote_stale(self, ticker: str, max_age_seconds: int = 60) -> bool:
        """
        Check if quote is stale (too old)
        
        Args:
            ticker: Ticker symbol
            max_age_seconds: Maximum acceptable age in seconds
            
        Returns:
            bool: True if quote is stale or missing
        """
        age = self.get_quote_age(ticker)
        if age is None:
            return True
        return age > max_age_seconds
    
    def start_polling(self, interval_seconds: int = 30):
        """
        Start periodic polling for quote updates
        
        Args:
            interval_seconds: Polling interval
        """
        if not self._connected:
            logger.error("Cannot start polling: not connected")
            return
        
        logger.info(f"Starting quote polling every {interval_seconds} seconds")
        
        try:
            while self._connected:
                self.refresh_quotes()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Polling stopped by user")
        except Exception as e:
            logger.error(f"Error in polling loop: {e}")
    
    def get_statistics(self) -> Dict:
        """
        Get handler statistics
        
        Returns:
            Dictionary with stats
        """
        return {
            'connected': self._connected,
            'subscribed_tickers': len(self._subscribed_tickers),
            'quotes_cached': len(self._quotes),
            'market_status': self.get_market_status(),
            'callbacks_registered': len(self._quote_callbacks)
        }
    
    def __repr__(self) -> str:
        return (f"RealtimeDataHandler(connected={self._connected}, "
                f"subscribed={len(self._subscribed_tickers)}, "
                f"quotes={len(self._quotes)})")
