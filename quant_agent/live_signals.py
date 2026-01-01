"""
Live Signal Generator
Runs scheduled scans and generates trading signals in real-time
"""

import logging
from datetime import datetime, time as dt_time
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import pandas as pd
import pytz

from .factors import FactorCalculator
from .scoring import Scorer
from .market_regime import MarketRegimeDetector
from .portfolio_correlation import PortfolioCorrelationManager
from .earnings_calendar import EarningsCalendarFilter

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Trading signal with all relevant data"""
    ticker: str
    timestamp: datetime
    composite_score: float
    price: float
    signal_type: str  # 'buy' or 'sell'
    
    # Factors
    factors: Dict
    
    # Trade plan
    shares: int
    stop_loss: float
    take_profit: float
    max_hold_days: int
    
    # Metadata
    rank: int
    market_regime: str
    scan_type: str  # 'premarket', 'market_hours', 'on_demand'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def __repr__(self) -> str:
        return (f"Signal({self.ticker} @ ${self.price:.2f}, "
                f"score={self.composite_score:.1f}, "
                f"shares={self.shares})")


class LiveSignalGenerator:
    """
    Generates trading signals in real-time
    
    Features:
    - Scheduled scanning (9:00 AM, 10:00 AM EST)
    - Factor calculation from live data
    - Signal filtering and ranking
    - Trade plan generation
    - Signal persistence
    """
    
    def __init__(self, 
                 data_loader,
                 realtime_handler,
                 config,
                 db_manager=None,
                 timezone: str = 'America/New_York'):
        """
        Initialize signal generator
        
        Args:
            data_loader: Data loader for historical data
            realtime_handler: Real-time data handler
            config: BacktestConfig or trading configuration
            db_manager: Database manager (optional)
            timezone: Market timezone
        """
        self.data_loader = data_loader
        self.realtime_handler = realtime_handler
        self.config = config
        self.db_manager = db_manager
        self.timezone = pytz.timezone(timezone)
        
        # Initialize components
        self.factor_calculator = FactorCalculator()
        self.scorer = Scorer()
        
        # Optional filters
        self.regime_detector = None
        self.correlation_manager = None
        self.earnings_filter = None
        
        if config.enable_regime_filter:
            try:
                self.regime_detector = MarketRegimeDetector(data_loader)
                logger.info("Market regime filter enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize regime detector: {e}")
        
        if config.enable_correlation_filter:
            try:
                self.correlation_manager = PortfolioCorrelationManager(data_loader)
                logger.info("Correlation filter enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize correlation manager: {e}")
        
        if config.enable_earnings_filter:
            try:
                self.earnings_filter = EarningsCalendarFilter()
                logger.info("Earnings filter enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize earnings filter: {e}")
        
        # Signal storage
        self.last_signals: List[Signal] = []
        self.last_scan_time: Optional[datetime] = None
        
        logger.info("LiveSignalGenerator initialized")
    
    def should_run_premarket_scan(self) -> bool:
        """
        Check if should run pre-market scan
        
        Returns:
            bool: True if time for pre-market scan (around 9:00 AM EST)
        """
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        # Run between 8:55 AM and 9:05 AM EST
        scan_start = dt_time(8, 55)
        scan_end = dt_time(9, 5)
        
        if not (scan_start <= current_time <= scan_end):
            return False
        
        # Don't run if already scanned recently (within 10 minutes)
        if self.last_scan_time:
            minutes_since_scan = (now - self.last_scan_time).total_seconds() / 60
            if minutes_since_scan < 10:
                return False
        
        return True
    
    def should_run_market_scan(self) -> bool:
        """
        Check if should run market hours scan
        
        Returns:
            bool: True if time for market scan (around 10:00 AM EST)
        """
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        # Run between 9:55 AM and 10:05 AM EST
        scan_start = dt_time(9, 55)
        scan_end = dt_time(10, 5)
        
        if not (scan_start <= current_time <= scan_end):
            return False
        
        # Don't run if already scanned recently (within 10 minutes)
        if self.last_scan_time:
            minutes_since_scan = (now - self.last_scan_time).total_seconds() / 60
            if minutes_since_scan < 10:
                return False
        
        return True
    
    def run_scan(self, tickers: List[str], scan_type: str = 'on_demand') -> List[Signal]:
        """
        Run a complete signal generation scan
        
        Args:
            tickers: List of tickers to scan
            scan_type: Type of scan ('premarket', 'market_hours', 'on_demand')
            
        Returns:
            List of generated signals
        """
        logger.info(f"Starting {scan_type} scan for {len(tickers)} tickers")
        start_time = datetime.now(self.timezone)
        
        signals = []
        
        # Get market regime
        market_regime = 'unknown'
        if self.regime_detector:
            try:
                regime = self.regime_detector.get_market_regime()
                market_regime = regime.get('regime', 'unknown')
                logger.info(f"Market regime: {market_regime}")
            except Exception as e:
                logger.warning(f"Failed to get market regime: {e}")
        
        # Calculate factors and scores for each ticker
        ticker_data = []
        for ticker in tickers:
            try:
                # Get historical data for factor calculation
                df = self.data_loader.download_ticker(ticker, period='60d', use_cache=True)
                
                if df is None or len(df) < 20:
                    logger.warning(f"Insufficient data for {ticker}")
                    continue
                
                # Calculate factors
                factors = self.factor_calculator.calculate_all_factors(df, ticker)
                
                if not factors:
                    logger.warning(f"No factors calculated for {ticker}")
                    continue
                
                # Get current price (from real-time if available, else from df)
                current_price = self.realtime_handler.get_last_price(ticker)
                if current_price is None:
                    current_price = float(df['Close'].iloc[-1])
                
                ticker_data.append({
                    'ticker': ticker,
                    'factors': factors,
                    'price': current_price,
                    'df': df
                })
                
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                continue
        
        if not ticker_data:
            logger.warning("No ticker data available for scoring")
            return []
        
        # Score all tickers (cross-sectional z-scores)
        try:
            # Calculate z-scores first (cross-sectional)
            factors_list = [t['factors'] for t in ticker_data]
            scored_factors = self.scorer.calculate_z_scores(factors_list)
            
            # Calculate composite scores
            for i, t in enumerate(ticker_data):
                scored = scored_factors[i]
                t['score'] = self.scorer.calculate_composite_score(scored)
            
        except Exception as e:
            logger.error(f"Error calculating scores: {e}")
            return []
        
        # Filter by minimum score threshold
        ticker_data = [t for t in ticker_data if t['score'] >= self.config.min_score_threshold]
        
        if not ticker_data:
            logger.info("No tickers above score threshold")
            return []
        
        # Sort by score (descending)
        ticker_data.sort(key=lambda x: x['score'], reverse=True)
        
        # Apply filters and generate signals
        for rank, t in enumerate(ticker_data, 1):
            try:
                # Apply earnings filter
                if self.earnings_filter:
                    if not self.earnings_filter.should_trade(t['ticker'], datetime.now()):
                        logger.info(f"Filtered {t['ticker']} due to earnings")
                        continue
                
                # Generate trade plan
                trade_plan = self._generate_trade_plan(
                    ticker=t['ticker'],
                    price=t['price'],
                    factors=t['factors'],
                    score=t['score']
                )
                
                # Create signal
                signal = Signal(
                    ticker=t['ticker'],
                    timestamp=start_time,
                    composite_score=t['score'],
                    price=t['price'],
                    signal_type='buy',
                    factors=t['factors'],
                    shares=trade_plan['shares'],
                    stop_loss=trade_plan['stop_loss'],
                    take_profit=trade_plan['take_profit'],
                    max_hold_days=trade_plan['max_hold_days'],
                    rank=rank,
                    market_regime=market_regime,
                    scan_type=scan_type
                )
                
                signals.append(signal)
                logger.info(f"Generated signal: {signal}")
                
            except Exception as e:
                logger.error(f"Error generating signal for {t['ticker']}: {e}")
                continue
        
        # Apply correlation filter if we have multiple signals
        if self.correlation_manager and len(signals) > 1:
            try:
                signals = self._apply_correlation_filter(signals)
            except Exception as e:
                logger.warning(f"Failed to apply correlation filter: {e}")
        
        # Update state
        self.last_signals = signals
        self.last_scan_time = start_time
        
        elapsed = (datetime.now(self.timezone) - start_time).total_seconds()
        logger.info(f"Scan complete: {len(signals)} signals generated in {elapsed:.1f}s")
        
        # Save to database if available
        if self.db_manager:
            try:
                self._save_signals_to_db(signals, scan_type)
            except Exception as e:
                logger.error(f"Failed to save signals to database: {e}")
        
        return signals
    
    def _generate_trade_plan(self, ticker: str, price: float, 
                            factors: Dict, score: float) -> Dict:
        """
        Generate trade plan (position size, stops, targets)
        
        Args:
            ticker: Ticker symbol
            price: Current price
            factors: Calculated factors
            score: Composite score
            
        Returns:
            Dictionary with trade plan
        """
        # Position sizing based on score and volatility
        volatility = factors.get('volatility_20d', 0.02)
        
        # Risk 1% of capital per trade
        risk_per_trade = self.config.initial_capital * 0.01
        
        # Stop loss at 2% below entry
        stop_loss_pct = 0.02
        stop_loss = price * (1 - stop_loss_pct)
        
        # Calculate position size
        risk_per_share = price - stop_loss
        shares = int(risk_per_trade / risk_per_share) if risk_per_share > 0 else 0
        
        # Limit position to max % of capital
        max_position_value = self.config.initial_capital * (self.config.max_position_pct / 100)
        max_shares = int(max_position_value / price)
        shares = min(shares, max_shares)
        
        # Take profit at 2:1 reward/risk
        take_profit_pct = stop_loss_pct * 2
        take_profit = price * (1 + take_profit_pct)
        
        # Max hold days based on score
        if score >= 80:
            max_hold_days = 7
        elif score >= 60:
            max_hold_days = 5
        else:
            max_hold_days = 3
        
        return {
            'shares': shares,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'max_hold_days': max_hold_days,
            'risk_per_share': risk_per_share,
            'position_value': shares * price
        }
    
    def _apply_correlation_filter(self, signals: List[Signal]) -> List[Signal]:
        """
        Filter signals based on correlation
        
        Args:
            signals: List of signals
            
        Returns:
            Filtered list of signals
        """
        if not signals:
            return signals
        
        # Get correlation matrix for signal tickers
        tickers = [s.ticker for s in signals]
        
        # For now, keep top N signals (correlation filter will be more sophisticated)
        max_positions = self.config.max_positions
        return signals[:max_positions]
    
    def _save_signals_to_db(self, signals: List[Signal], scan_type: str):
        """
        Save signals to database
        
        Args:
            signals: List of signals to save
            scan_type: Type of scan
        """
        # TODO: Implement database persistence
        logger.info(f"Saving {len(signals)} signals to database (scan_type={scan_type})")
        pass
    
    def get_last_signals(self) -> List[Signal]:
        """
        Get signals from last scan
        
        Returns:
            List of signals
        """
        return self.last_signals
    
    def compare_with_previous(self, new_signals: List[Signal]) -> Dict:
        """
        Compare new signals with previous scan
        
        Args:
            new_signals: Newly generated signals
            
        Returns:
            Dictionary with comparison stats
        """
        if not self.last_signals:
            return {
                'new_tickers': [s.ticker for s in new_signals],
                'removed_tickers': [],
                'common_tickers': []
            }
        
        previous_tickers = set(s.ticker for s in self.last_signals)
        new_tickers_set = set(s.ticker for s in new_signals)
        
        return {
            'new_tickers': list(new_tickers_set - previous_tickers),
            'removed_tickers': list(previous_tickers - new_tickers_set),
            'common_tickers': list(previous_tickers & new_tickers_set)
        }
    
    def get_statistics(self) -> Dict:
        """
        Get generator statistics
        
        Returns:
            Dictionary with stats
        """
        return {
            'last_scan_time': self.last_scan_time,
            'last_scan_signals': len(self.last_signals),
            'filters_enabled': {
                'regime': self.regime_detector is not None,
                'correlation': self.correlation_manager is not None,
                'earnings': self.earnings_filter is not None
            }
        }
    
    def __repr__(self) -> str:
        return (f"LiveSignalGenerator(last_scan={self.last_scan_time}, "
                f"signals={len(self.last_signals)})")
