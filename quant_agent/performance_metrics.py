"""Performance metrics calculator for backtest analysis."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger


class PerformanceMetrics:
    """Calculate comprehensive performance metrics from backtest results."""
    
    # Target metrics for strategy validation
    TARGET_SHARPE = 1.5
    TARGET_MAX_DRAWDOWN = 20.0  # %
    TARGET_WIN_RATE = 45.0  # %
    TARGET_PROFIT_FACTOR = 1.5
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sharpe ratio.
        
        Args:
            returns: Series of returns
            risk_free_rate: Risk-free rate (annualized)
            periods_per_year: Number of periods per year
            
        Returns:
            Sharpe ratio
        """
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        sharpe = excess_returns.mean() / returns.std()
        sharpe_annualized = sharpe * np.sqrt(periods_per_year)
        
        return sharpe_annualized
    
    @staticmethod
    def calculate_sortino_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sortino ratio (downside deviation only).
        
        Args:
            returns: Series of returns
            risk_free_rate: Risk-free rate
            periods_per_year: Number of periods per year
            
        Returns:
            Sortino ratio
        """
        if len(returns) == 0:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        sortino = excess_returns.mean() / downside_returns.std()
        sortino_annualized = sortino * np.sqrt(periods_per_year)
        
        return sortino_annualized
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> Dict[str, float]:
        """
        Calculate maximum drawdown.
        
        Args:
            equity_curve: Series of equity values
            
        Returns:
            Dictionary with max_drawdown_pct, max_drawdown_duration
        """
        if len(equity_curve) == 0:
            return {'max_drawdown_pct': 0.0, 'max_drawdown_duration': 0}
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown
        drawdown = (equity_curve - running_max) / running_max * 100
        
        max_drawdown_pct = abs(drawdown.min())
        
        # Calculate drawdown duration
        is_drawdown = drawdown < 0
        drawdown_periods = is_drawdown.astype(int).groupby(
            (is_drawdown != is_drawdown.shift()).cumsum()
        ).sum()
        
        max_drawdown_duration = drawdown_periods.max() if len(drawdown_periods) > 0 else 0
        
        return {
            'max_drawdown_pct': max_drawdown_pct,
            'max_drawdown_duration': int(max_drawdown_duration)
        }
    
    @staticmethod
    def calculate_win_rate(trades: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate win rate and related metrics.
        
        Args:
            trades: DataFrame with trade results
            
        Returns:
            Dictionary with win metrics
        """
        if len(trades) == 0:
            return {
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'total_wins': 0,
                'total_losses': 0
            }
        
        winning_trades = trades[trades['pnl'] > 0]
        losing_trades = trades[trades['pnl'] < 0]
        
        win_rate = (len(winning_trades) / len(trades)) * 100
        
        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0.0
        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0.0
        
        largest_win = winning_trades['pnl'].max() if len(winning_trades) > 0 else 0.0
        largest_loss = losing_trades['pnl'].min() if len(losing_trades) > 0 else 0.0
        
        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'total_wins': len(winning_trades),
            'total_losses': len(losing_trades)
        }
    
    @staticmethod
    def calculate_profit_factor(trades: pd.DataFrame) -> float:
        """
        Calculate profit factor (gross profit / gross loss).
        
        Args:
            trades: DataFrame with trade results
            
        Returns:
            Profit factor
        """
        if len(trades) == 0:
            return 0.0
        
        gross_profit = trades[trades['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades[trades['pnl'] < 0]['pnl'].sum())
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    @staticmethod
    def calculate_cagr(
        initial_capital: float,
        final_equity: float,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """
        Calculate Compound Annual Growth Rate.
        
        Args:
            initial_capital: Starting capital
            final_equity: Ending equity
            start_date: Start date
            end_date: End date
            
        Returns:
            CAGR percentage
        """
        if initial_capital <= 0:
            return 0.0
        
        years = (end_date - start_date).days / 365.25
        
        if years <= 0:
            return 0.0
        
        cagr = ((final_equity / initial_capital) ** (1 / years) - 1) * 100
        
        return cagr
    
    @staticmethod
    def calculate_calmar_ratio(
        cagr: float,
        max_drawdown_pct: float
    ) -> float:
        """
        Calculate Calmar ratio (CAGR / Max Drawdown).
        
        Args:
            cagr: Compound annual growth rate
            max_drawdown_pct: Maximum drawdown percentage
            
        Returns:
            Calmar ratio
        """
        if max_drawdown_pct == 0:
            return 0.0
        
        return cagr / max_drawdown_pct
    
    @staticmethod
    def calculate_expectancy(trades: pd.DataFrame) -> float:
        """
        Calculate expectancy (average trade profit).
        
        Args:
            trades: DataFrame with trade results
            
        Returns:
            Expectancy per trade
        """
        if len(trades) == 0:
            return 0.0
        
        return trades['pnl'].mean()
    
    @staticmethod
    def calculate_kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly criterion percentage.
        
        Args:
            win_rate: Win rate (0-100)
            avg_win: Average winning trade
            avg_loss: Average losing trade (positive number)
            
        Returns:
            Kelly percentage (0-100)
        """
        if avg_loss == 0 or win_rate == 0:
            return 0.0
        
        win_prob = win_rate / 100
        loss_prob = 1 - win_prob
        
        win_loss_ratio = avg_win / abs(avg_loss)
        
        kelly = (win_prob * win_loss_ratio - loss_prob) / win_loss_ratio
        
        return max(0, min(100, kelly * 100))
    
    @staticmethod
    def regime_specific_performance(
        trades: pd.DataFrame,
        equity_curve: pd.DataFrame
    ) -> Dict[str, Dict]:
        """
        Calculate performance by market regime.
        
        Args:
            trades: Trade log
            equity_curve: Equity curve with regime info
            
        Returns:
            Dictionary of regime -> metrics
        """
        # This would require regime info in trades
        # Placeholder for now
        return {
            'bull': {},
            'bear': {},
            'sideways': {}
        }
    
    @staticmethod
    def analyze_exit_reasons(trades: pd.DataFrame) -> Dict[str, int]:
        """
        Analyze trade exit reasons.
        
        Args:
            trades: Trade log
            
        Returns:
            Dictionary of exit_reason -> count
        """
        if len(trades) == 0:
            return {}
        
        exit_counts = trades['exit_reason'].value_counts().to_dict()
        
        return exit_counts
    
    @staticmethod
    def calculate_comprehensive_metrics(
        trades: pd.DataFrame,
        equity_curve: pd.DataFrame,
        initial_capital: float,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Calculate all performance metrics.
        
        Args:
            trades: Trade log DataFrame
            equity_curve: Equity curve DataFrame
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date
            
        Returns:
            Comprehensive metrics dictionary
        """
        logger.info("Calculating performance metrics...")
        
        # Basic metrics
        final_equity = equity_curve.iloc[-1]['equity'] if len(equity_curve) > 0 else initial_capital
        total_return = ((final_equity - initial_capital) / initial_capital) * 100
        
        # Calculate returns
        equity_series = equity_curve.set_index('date')['equity']
        daily_returns = equity_series.pct_change().dropna()
        
        # Risk metrics
        sharpe = PerformanceMetrics.calculate_sharpe_ratio(daily_returns)
        sortino = PerformanceMetrics.calculate_sortino_ratio(daily_returns)
        drawdown_metrics = PerformanceMetrics.calculate_max_drawdown(equity_series)
        
        # Trade metrics
        win_metrics = PerformanceMetrics.calculate_win_rate(trades)
        profit_factor = PerformanceMetrics.calculate_profit_factor(trades)
        expectancy = PerformanceMetrics.calculate_expectancy(trades)
        
        # Time-based metrics
        cagr = PerformanceMetrics.calculate_cagr(initial_capital, final_equity, start_date, end_date)
        calmar = PerformanceMetrics.calculate_calmar_ratio(cagr, drawdown_metrics['max_drawdown_pct'])
        
        # Kelly criterion
        kelly = PerformanceMetrics.calculate_kelly_criterion(
            win_metrics['win_rate'],
            win_metrics['avg_win'],
            abs(win_metrics['avg_loss'])
        )
        
        # Exit analysis
        exit_reasons = PerformanceMetrics.analyze_exit_reasons(trades)
        
        # Compile results
        metrics = {
            'overview': {
                'total_trades': len(trades),
                'total_return_pct': total_return,
                'initial_capital': initial_capital,
                'final_equity': final_equity,
                'net_profit': final_equity - initial_capital
            },
            'risk_adjusted': {
                'sharpe_ratio': sharpe,
                'sortino_ratio': sortino,
                'calmar_ratio': calmar,
                'max_drawdown_pct': drawdown_metrics['max_drawdown_pct'],
                'max_drawdown_duration_days': drawdown_metrics['max_drawdown_duration']
            },
            'trade_quality': {
                'win_rate_pct': win_metrics['win_rate'],
                'profit_factor': profit_factor,
                'expectancy': expectancy,
                'avg_win': win_metrics['avg_win'],
                'avg_loss': win_metrics['avg_loss'],
                'largest_win': win_metrics['largest_win'],
                'largest_loss': win_metrics['largest_loss'],
                'total_wins': win_metrics['total_wins'],
                'total_losses': win_metrics['total_losses']
            },
            'time_based': {
                'cagr_pct': cagr,
                'trading_days': len(equity_curve),
                'avg_hold_days': trades['hold_days'].mean() if len(trades) > 0 else 0
            },
            'position_sizing': {
                'kelly_criterion_pct': kelly,
                'suggested_risk_pct': kelly / 2  # Half Kelly for safety
            },
            'exit_analysis': exit_reasons,
            'validation': {
                'meets_sharpe_target': sharpe >= PerformanceMetrics.TARGET_SHARPE,
                'meets_drawdown_target': drawdown_metrics['max_drawdown_pct'] <= PerformanceMetrics.TARGET_MAX_DRAWDOWN,
                'meets_win_rate_target': win_metrics['win_rate'] >= PerformanceMetrics.TARGET_WIN_RATE,
                'meets_profit_factor_target': profit_factor >= PerformanceMetrics.TARGET_PROFIT_FACTOR,
                'passes_all_criteria': (
                    sharpe >= PerformanceMetrics.TARGET_SHARPE and
                    drawdown_metrics['max_drawdown_pct'] <= PerformanceMetrics.TARGET_MAX_DRAWDOWN and
                    win_metrics['win_rate'] >= PerformanceMetrics.TARGET_WIN_RATE and
                    profit_factor >= PerformanceMetrics.TARGET_PROFIT_FACTOR
                )
            }
        }
        
        # Log summary
        logger.info(f"✓ Performance Summary:")
        logger.info(f"  Total Return: {total_return:.2f}%")
        logger.info(f"  Sharpe Ratio: {sharpe:.2f} (target: {PerformanceMetrics.TARGET_SHARPE})")
        logger.info(f"  Max Drawdown: {drawdown_metrics['max_drawdown_pct']:.2f}% (target: <{PerformanceMetrics.TARGET_MAX_DRAWDOWN}%)")
        logger.info(f"  Win Rate: {win_metrics['win_rate']:.2f}% (target: >{PerformanceMetrics.TARGET_WIN_RATE}%)")
        logger.info(f"  Profit Factor: {profit_factor:.2f} (target: >{PerformanceMetrics.TARGET_PROFIT_FACTOR})")
        logger.info(f"  Passes All Criteria: {metrics['validation']['passes_all_criteria']}")
        
        return metrics


# Global instance
performance_metrics = PerformanceMetrics()
