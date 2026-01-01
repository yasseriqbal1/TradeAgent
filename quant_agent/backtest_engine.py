"""Backtesting engine for trade strategy validation."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger

from .historical_data import historical_data_manager
from .factors import FactorCalculator
from .scoring import Scorer
from .risk_management import risk_manager
from .market_regime import market_regime_detector
from .portfolio_correlation import portfolio_correlation_manager
from .earnings_calendar import earnings_filter


@dataclass
class Trade:
    """Single trade record."""
    ticker: str
    entry_date: datetime
    entry_price: float
    position_size: int
    stop_loss: float
    take_profit: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    hold_days: Optional[int] = None
    
    def is_open(self) -> bool:
        """Check if trade is still open."""
        return self.exit_date is None
    
    def close_trade(
        self,
        exit_date: datetime,
        exit_price: float,
        exit_reason: str,
        commission: float = 1.0
    ):
        """Close the trade and calculate P&L."""
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        
        # Calculate P&L
        gross_pnl = (exit_price - self.entry_price) * self.position_size
        self.pnl = gross_pnl - (2 * commission)  # Entry + exit commission
        self.pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
        
        # Calculate hold days
        self.hold_days = (exit_date - self.entry_date).days


@dataclass
class BacktestConfig:
    """Backtesting configuration."""
    initial_capital: float = 100000.0
    max_positions: int = 3
    max_hold_days: int = 5
    max_position_pct: float = 40.0  # Max % of capital per position
    commission_per_trade: float = 1.0
    slippage_pct: float = 0.05  # 0.05% slippage
    min_score_threshold: float = 60.0
    enable_regime_filter: bool = True
    enable_correlation_filter: bool = True
    enable_earnings_filter: bool = True


class Backtester:
    """Backtesting engine for strategy validation."""
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        
        # Backtest state
        self.trades: List[Trade] = []
        self.open_positions: List[Trade] = []
        self.equity_curve = []
        self.daily_returns = []
        
        # Performance tracking
        self.current_capital = self.config.initial_capital
        self.peak_equity = self.config.initial_capital
        
    def load_historical_data(
        self,
        tickers: List[str],
        start_date: datetime,
        end_date: datetime,
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Load historical data for backtesting.
        
        Args:
            tickers: List of tickers to test
            start_date: Start date for backtest
            end_date: End date for backtest
            force_refresh: Force download fresh data
            
        Returns:
            Dictionary of ticker -> DataFrame with OHLCV data
        """
        logger.info(f"Loading historical data for {len(tickers)} tickers...")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        
        # Download data
        data = historical_data_manager.download_historical_data(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            force_refresh=force_refresh
        )
        
        # Validate each ticker's data
        for ticker, df in data.items():
            validation = historical_data_manager.validate_data(df, ticker)
            if not validation['valid']:
                logger.warning(f"{ticker} validation issues: {validation['issues']}")
        
        # Get aligned data
        aligned_data = historical_data_manager.get_aligned_data(data)
        
        logger.info(f"✓ Loaded {len(aligned_data)} tickers with {len(next(iter(aligned_data.values())))} bars each")
        
        return aligned_data
    
    def calculate_signals(
        self,
        data: Dict[str, pd.DataFrame],
        current_date: datetime
    ) -> List[Dict]:
        """
        Calculate trading signals for current date.
        
        Args:
            data: Historical data
            current_date: Date to calculate signals for
            
        Returns:
            List of signals with scores and trade plans
        """
        signals = []
        
        tickers_checked = 0
        tickers_passed_length = 0
        tickers_with_factors = 0
        tickers_with_trade_plans = 0
        tickers_with_signals = 0
        
        for ticker, df in data.items():
            tickers_checked += 1
            # Get data up to current date (no lookahead bias)
            historical_df = df[df.index <= current_date].copy()
            
            # Require at least 21 days for basic factors (14 for RSI + 7 buffer)
            if len(historical_df) < 21:
                logger.debug(f"{ticker}: Insufficient data ({len(historical_df)} < 21 days)")
                continue
            
            tickers_passed_length += 1
            logger.debug(f"{ticker}: Has {len(historical_df)} days of data")
            
            try:
                # Calculate factors
                factors = FactorCalculator.calculate_all_factors(historical_df, ticker)
                
                if factors is None:
                    logger.debug(f"{ticker}: Factors calculation returned None")
                    continue
                
                tickers_with_factors += 1
                logger.debug(f"{ticker}: Factors calculated successfully")
                
                # Calculate score using absolute factor values (not z-scores)
                # Since we're evaluating tickers sequentially, we can't do cross-sectional z-scores
                # Use a simple weighted score based on normalized individual factors
                
                # Momentum: 20-day return is key (range typically -50% to +100%)
                momentum_score = factors.get('return_20d', 0) * 100  # Scale to similar range as others
                
                # RSI: Neutral is 50, overbought >70, oversold <30
                rsi = factors.get('rsi_14', 50)
                rsi_score = 0
                if 40 < rsi < 60:  # Neutral range - moderate signal
                    rsi_score = 5
                elif 30 < rsi <= 40:  # Oversold - potential buy
                    rsi_score = 10  
                elif rsi < 30:  # Very oversold - strong buy
                    rsi_score = 15
                
                # Volume: Higher volume ratio is better (typically 0.5 to 3.0)
                volume_ratio = factors.get('volume_ratio', 1.0)
                volume_score = (volume_ratio - 1.0) * 10  # Above average = positive
                
                # Combine with weights
                score = (
                    momentum_score * 0.5 +  # 50% weight on momentum
                    rsi_score * 0.2 +  # 20% weight on RSI
                    volume_score * 0.3  # 30% weight on volume
                )
                
                logger.debug(f"{ticker}: Score components - momentum={momentum_score:.2f}, rsi={rsi_score:.2f}, volume={volume_score:.2f}")
                logger.debug(f"{ticker}: Composite score = {score:.4f} (threshold = {self.config.min_score_threshold})")
                
                
                
                # Get current price (use uppercase 'Close' to match data columns)
                current_price = historical_df.iloc[-1]['Close']
                
                # Generate trade plan (use 'price' not 'current_price')
                trade_plan = risk_manager.generate_trade_plan(
                    ticker=ticker,
                    price=current_price,
                    atr=factors.get('atr', current_price * 0.02),  # Fallback to 2% if no ATR
                    composite_score=score,
                    factors=factors,
                    direction='long'
                )
                
                if not trade_plan:
                    logger.debug(f"{ticker}: Trade plan generation returned None")
                    continue
                
                tickers_with_trade_plans += 1
                
                if score >= self.config.min_score_threshold:
                    tickers_with_signals += 1
                    signals.append({
                        'ticker': ticker,
                        'date': current_date,
                        'score': score,
                        'price': current_price,
                        'factors': factors,
                        'trade_plan': trade_plan
                    })
                    logger.debug(f"{ticker}: Signal generated successfully")
                else:
                    logger.debug(f"{ticker}: Score below threshold ({score:.4f} < {self.config.min_score_threshold})")
                    
            except Exception as e:
                logger.debug(f"Error calculating signals for {ticker}: {e}")
                continue
        
        logger.info(f"Signal generation for {current_date.date()}: Checked {tickers_checked} tickers, "
                   f"{tickers_passed_length} passed length check, {tickers_with_factors} calculated factors, "
                   f"{tickers_with_trade_plans} got trade plans, {tickers_with_signals} generated signals")
        
        # Sort by score
        signals.sort(key=lambda x: x['score'], reverse=True)
        
        return signals
    
    def apply_filters(
        self,
        signals: List[Dict],
        current_date: datetime
    ) -> List[Dict]:
        """
        Apply regime, correlation, and earnings filters.
        
        Args:
            signals: List of signals to filter
            current_date: Current date for regime detection
            
        Returns:
            Filtered signals
        """
        if not signals:
            return []
        
        filtered = signals.copy()
        
        # 1. Market regime filter
        if self.config.enable_regime_filter:
            # Get market regime (uses SPY data loaded internally)
            regime = market_regime_detector.get_market_regime()
            
            # Don't trade in extreme conditions
            if not market_regime_detector.should_trade_today(regime):
                logger.info(f"Market regime filter: No trading today ({regime['overall_regime']})")
                return []
        
        # 2. Earnings filter
        if self.config.enable_earnings_filter:
            safe_signals, earnings_filtered = earnings_filter.filter_earnings_stocks(
                signals=filtered,
                reference_date=current_date
            )
            filtered = safe_signals
        
        # 3. Correlation filter
        if self.config.enable_correlation_filter and self.open_positions:
            correlation_filtered = []
            
            for signal in filtered:
                # Check correlation with existing positions
                existing_tickers = [pos.ticker for pos in self.open_positions]
                
                # Would validate using historical returns
                # For now, simple check
                correlation_filtered.append(signal)
            
            filtered = correlation_filtered
        
        return filtered
    
    def simulate_trades(
        self,
        data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime
    ):
        """
        Run backtest simulation.
        
        Args:
            data: Historical price data
            start_date: Start date for simulation
            end_date: End date for simulation
        """
        logger.info("Starting backtest simulation...")
        
        # Get trading dates
        sample_df = next(iter(data.values()))
        
        # Make start_date and end_date timezone-aware if needed
        if sample_df.index.tz is not None and start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=sample_df.index.tz)
        if sample_df.index.tz is not None and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=sample_df.index.tz)
        
        all_dates = sample_df[(sample_df.index >= start_date) & (sample_df.index <= end_date)].index
        
        for current_date in all_dates:
            # Check and close positions first
            self._check_exits(data, current_date)
            
            # Record daily equity
            total_equity = self._calculate_total_equity(data, current_date)
            self.equity_curve.append({
                'date': current_date,
                'equity': total_equity,
                'cash': self.current_capital,
                'positions': len(self.open_positions)
            })
            
            # Update peak for drawdown calculation
            if total_equity > self.peak_equity:
                self.peak_equity = total_equity
            
            # Generate new signals if we have room
            if len(self.open_positions) < self.config.max_positions:
                signals = self.calculate_signals(data, current_date)
                filtered_signals = self.apply_filters(signals, current_date)
                
                # Enter new positions
                positions_to_open = self.config.max_positions - len(self.open_positions)
                for signal in filtered_signals[:positions_to_open]:
                    self._enter_position(data, signal, current_date)
        
        # Close any remaining open positions at end
        for position in self.open_positions[:]:
            self._exit_position(
                position=position,
                exit_date=end_date,
                exit_price=data[position.ticker].loc[end_date, 'Close'],
                exit_reason='backtest_end'
            )
        
        logger.info(f"✓ Backtest complete: {len(self.trades)} trades executed")
    
    def _check_exits(
        self,
        data: Dict[str, pd.DataFrame],
        current_date: datetime
    ):
        """Check if any open positions should be closed."""
        for position in self.open_positions[:]:
            ticker_data = data[position.ticker]
            
            # Get current bar
            if current_date not in ticker_data.index:
                continue
            
            current_bar = ticker_data.loc[current_date]
            
            # Check stop loss
            if current_bar['Low'] <= position.stop_loss:
                exit_price = position.stop_loss * (1 - self.config.slippage_pct / 100)
                self._exit_position(position, current_date, exit_price, 'stop_loss')
                continue
            
            # Check take profit
            if current_bar['High'] >= position.take_profit:
                exit_price = position.take_profit * (1 - self.config.slippage_pct / 100)
                self._exit_position(position, current_date, exit_price, 'take_profit')
                continue
            
            # Check max hold time
            hold_days = (current_date - position.entry_date).days
            if hold_days >= self.config.max_hold_days:
                exit_price = current_bar['Close'] * (1 - self.config.slippage_pct / 100)
                self._exit_position(position, current_date, exit_price, 'max_hold')
                continue
    
    def _enter_position(
        self,
        data: Dict[str, pd.DataFrame],
        signal: Dict,
        entry_date: datetime
    ):
        """Enter a new position."""
        ticker = signal['ticker']
        trade_plan = signal['trade_plan']
        
        # Get next day open price (no lookahead bias)
        ticker_data = data[ticker]
        future_dates = ticker_data[ticker_data.index > entry_date].index
        
        if len(future_dates) == 0:
            return  # No future data
        
        next_date = future_dates[0]
        entry_price = ticker_data.loc[next_date, 'Open']
        
        # Apply slippage
        entry_price = entry_price * (1 + self.config.slippage_pct / 100)
        
        # Get position size from trade plan
        position_size = trade_plan.get('shares', 0)
        
        if position_size <= 0:
            return
        
        # Check if we have enough capital
        cost = position_size * entry_price + self.config.commission_per_trade
        
        if cost > self.current_capital:
            # Reduce position size to fit capital
            position_size = int((self.current_capital - self.config.commission_per_trade) / entry_price)
            
            if position_size <= 0:
                return
        
        # Create trade
        trade = Trade(
            ticker=ticker,
            entry_date=next_date,
            entry_price=entry_price,
            position_size=position_size,
            stop_loss=trade_plan['stop_loss'],
            take_profit=trade_plan['take_profit']
        )
        
        # Deduct capital
        self.current_capital -= (position_size * entry_price + self.config.commission_per_trade)
        
        # Add to open positions
        self.open_positions.append(trade)
        
        logger.debug(f"✓ Opened {ticker}: {position_size} @ ${entry_price:.2f}")
    
    def _exit_position(
        self,
        position: Trade,
        exit_date: datetime,
        exit_price: float,
        exit_reason: str
    ):
        """Exit an open position."""
        # Close trade
        position.close_trade(exit_date, exit_price, exit_reason, self.config.commission_per_trade)
        
        # Add capital back
        self.current_capital += (position.position_size * exit_price - self.config.commission_per_trade)
        
        # Move to closed trades
        self.open_positions.remove(position)
        self.trades.append(position)
        
        logger.debug(
            f"✓ Closed {position.ticker}: {exit_reason} "
            f"P&L=${position.pnl:.2f} ({position.pnl_pct:.2f}%)"
        )
    
    def _calculate_total_equity(
        self,
        data: Dict[str, pd.DataFrame],
        current_date: datetime
    ) -> float:
        """Calculate total equity (cash + positions)."""
        total = self.current_capital
        
        for position in self.open_positions:
            ticker_data = data[position.ticker]
            
            if current_date in ticker_data.index:
                current_price = ticker_data.loc[current_date, 'Close']
                position_value = position.position_size * current_price
                total += position_value
        
        return total
    
    def get_trade_log(self) -> pd.DataFrame:
        """Get DataFrame of all trades."""
        if not self.trades:
            return pd.DataFrame()
        
        trade_dicts = []
        for trade in self.trades:
            trade_dicts.append({
                'ticker': trade.ticker,
                'entry_date': trade.entry_date,
                'entry_price': trade.entry_price,
                'exit_date': trade.exit_date,
                'exit_price': trade.exit_price,
                'position_size': trade.position_size,
                'exit_reason': trade.exit_reason,
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct,
                'hold_days': trade.hold_days
            })
        
        return pd.DataFrame(trade_dicts)
    
    def get_equity_curve(self) -> pd.DataFrame:
        """Get equity curve DataFrame."""
        return pd.DataFrame(self.equity_curve)


# Global instance
backtester = Backtester()
