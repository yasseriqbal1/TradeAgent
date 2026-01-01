"""Walk-forward validation for strategy robustness testing."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass
from loguru import logger

from .backtest_engine import Backtester, BacktestConfig
from .performance_metrics import PerformanceMetrics


@dataclass
class WalkForwardWindow:
    """Single walk-forward testing window."""
    window_id: int
    start_date: datetime
    end_date: datetime
    window_type: str  # 'bull', 'bear', 'sideways', 'mixed'
    metrics: Dict = None


class WalkForwardValidator:
    """Walk-forward validation for strategy consistency testing."""
    
    def __init__(
        self,
        window_months: int = 6,
        overlap_months: int = 0
    ):
        """
        Initialize walk-forward validator.
        
        Args:
            window_months: Size of each testing window in months
            overlap_months: Overlap between windows
        """
        self.window_months = window_months
        self.overlap_months = overlap_months
        self.windows: List[WalkForwardWindow] = []
        self.aggregate_metrics = {}
    
    def create_windows(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[WalkForwardWindow]:
        """
        Create walk-forward testing windows.
        
        Args:
            start_date: Overall start date
            end_date: Overall end date
            
        Returns:
            List of testing windows
        """
        windows = []
        window_id = 1
        current_start = start_date
        
        while current_start < end_date:
            # Calculate window end
            window_end = current_start + timedelta(days=self.window_months * 30)
            window_end = min(window_end, end_date)
            
            # Create window
            window = WalkForwardWindow(
                window_id=window_id,
                start_date=current_start,
                end_date=window_end,
                window_type='mixed'  # Will be determined later
            )
            
            windows.append(window)
            
            # Move to next window
            advance_months = self.window_months - self.overlap_months
            current_start = current_start + timedelta(days=advance_months * 30)
            window_id += 1
        
        logger.info(f"✓ Created {len(windows)} walk-forward windows")
        
        self.windows = windows
        return windows
    
    def classify_window_type(
        self,
        spy_data: pd.DataFrame,
        window: WalkForwardWindow
    ) -> str:
        """
        Classify window as bull/bear/sideways market.
        
        Args:
            spy_data: SPY price data
            window: Window to classify
            
        Returns:
            Window type ('bull', 'bear', 'sideways')
        """
        # Get SPY data for window
        window_data = spy_data[
            (spy_data.index >= window.start_date) &
            (spy_data.index <= window.end_date)
        ]
        
        if len(window_data) == 0:
            return 'mixed'
        
        # Calculate return
        start_price = window_data.iloc[0]['close']
        end_price = window_data.iloc[-1]['close']
        total_return = ((end_price - start_price) / start_price) * 100
        
        # Calculate volatility
        returns = window_data['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100
        
        # Classify
        if total_return > 10 and volatility < 20:
            return 'bull'
        elif total_return < -10:
            return 'bear'
        elif abs(total_return) < 5:
            return 'sideways'
        else:
            return 'mixed'
    
    def run_walk_forward_test(
        self,
        data: Dict[str, pd.DataFrame],
        config: BacktestConfig = None
    ) -> Dict:
        """
        Run walk-forward validation.
        
        Args:
            data: Historical price data for all tickers
            config: Backtest configuration
            
        Returns:
            Walk-forward results dictionary
        """
        if not self.windows:
            logger.error("No windows created. Call create_windows() first.")
            return {}
        
        logger.info(f"Starting walk-forward test across {len(self.windows)} windows...")
        
        window_results = []
        
        for window in self.windows:
            logger.info(
                f"Testing window {window.window_id}: "
                f"{window.start_date.date()} to {window.end_date.date()}"
            )
            
            # Create backtester for this window
            backtester = Backtester(config=config)
            
            # Get tickers
            tickers = list(data.keys())
            
            # Run backtest for window
            backtester.simulate_trades(
                data=data,
                start_date=window.start_date,
                end_date=window.end_date
            )
            
            # Get results
            trades = backtester.get_trade_log()
            equity_curve = backtester.get_equity_curve()
            
            if len(equity_curve) == 0:
                logger.warning(f"Window {window.window_id}: No equity data")
                continue
            
            # Calculate metrics
            metrics = PerformanceMetrics.calculate_comprehensive_metrics(
                trades=trades,
                equity_curve=equity_curve,
                initial_capital=config.initial_capital if config else 100000.0,
                start_date=window.start_date,
                end_date=window.end_date
            )
            
            # Store metrics in window
            window.metrics = metrics
            
            # Add to results
            window_results.append({
                'window_id': window.window_id,
                'start_date': window.start_date,
                'end_date': window.end_date,
                'window_type': window.window_type,
                'total_trades': metrics['overview']['total_trades'],
                'total_return_pct': metrics['overview']['total_return_pct'],
                'sharpe_ratio': metrics['risk_adjusted']['sharpe_ratio'],
                'max_drawdown_pct': metrics['risk_adjusted']['max_drawdown_pct'],
                'win_rate_pct': metrics['trade_quality']['win_rate_pct'],
                'profit_factor': metrics['trade_quality']['profit_factor'],
                'passes_criteria': metrics['validation']['passes_all_criteria']
            })
        
        # Calculate aggregate statistics
        self.aggregate_metrics = self._calculate_aggregate_metrics(window_results)
        
        logger.info("✓ Walk-forward validation complete")
        
        return {
            'window_results': window_results,
            'aggregate_metrics': self.aggregate_metrics,
            'consistency_analysis': self._analyze_consistency(window_results)
        }
    
    def _calculate_aggregate_metrics(
        self,
        window_results: List[Dict]
    ) -> Dict:
        """
        Calculate aggregate metrics across all windows.
        
        Args:
            window_results: List of window results
            
        Returns:
            Aggregate metrics dictionary
        """
        if not window_results:
            return {}
        
        df = pd.DataFrame(window_results)
        
        aggregate = {
            'total_windows': len(window_results),
            'avg_sharpe': df['sharpe_ratio'].mean(),
            'std_sharpe': df['sharpe_ratio'].std(),
            'min_sharpe': df['sharpe_ratio'].min(),
            'max_sharpe': df['sharpe_ratio'].max(),
            'avg_return': df['total_return_pct'].mean(),
            'std_return': df['total_return_pct'].std(),
            'avg_max_drawdown': df['max_drawdown_pct'].mean(),
            'worst_drawdown': df['max_drawdown_pct'].max(),
            'avg_win_rate': df['win_rate_pct'].mean(),
            'avg_profit_factor': df['profit_factor'].mean(),
            'windows_passing_criteria': df['passes_criteria'].sum(),
            'pass_rate': (df['passes_criteria'].sum() / len(df)) * 100
        }
        
        logger.info(f"✓ Aggregate Metrics:")
        logger.info(f"  Avg Sharpe: {aggregate['avg_sharpe']:.2f} (±{aggregate['std_sharpe']:.2f})")
        logger.info(f"  Avg Return: {aggregate['avg_return']:.2f}%")
        logger.info(f"  Avg Max DD: {aggregate['avg_max_drawdown']:.2f}%")
        logger.info(f"  Pass Rate: {aggregate['pass_rate']:.1f}% ({aggregate['windows_passing_criteria']}/{aggregate['total_windows']})")
        
        return aggregate
    
    def _analyze_consistency(
        self,
        window_results: List[Dict]
    ) -> Dict:
        """
        Analyze strategy consistency across windows.
        
        Args:
            window_results: List of window results
            
        Returns:
            Consistency analysis dictionary
        """
        if len(window_results) < 2:
            return {}
        
        df = pd.DataFrame(window_results)
        
        # Check for degradation over time
        first_half = df.iloc[:len(df)//2]
        second_half = df.iloc[len(df)//2:]
        
        first_half_sharpe = first_half['sharpe_ratio'].mean()
        second_half_sharpe = second_half['sharpe_ratio'].mean()
        
        degradation = ((second_half_sharpe - first_half_sharpe) / first_half_sharpe) * 100 if first_half_sharpe != 0 else 0
        
        # Count consecutive failures
        failures = (~df['passes_criteria']).astype(int)
        max_consecutive_failures = 0
        current_failures = 0
        
        for failure in failures:
            if failure:
                current_failures += 1
                max_consecutive_failures = max(max_consecutive_failures, current_failures)
            else:
                current_failures = 0
        
        # Coefficient of variation for stability
        sharpe_cv = (df['sharpe_ratio'].std() / df['sharpe_ratio'].mean()) * 100 if df['sharpe_ratio'].mean() != 0 else 0
        return_cv = (df['total_return_pct'].std() / df['total_return_pct'].mean()) * 100 if df['total_return_pct'].mean() != 0 else 0
        
        consistency = {
            'first_half_sharpe': first_half_sharpe,
            'second_half_sharpe': second_half_sharpe,
            'performance_degradation_pct': degradation,
            'max_consecutive_failures': max_consecutive_failures,
            'sharpe_coefficient_of_variation': sharpe_cv,
            'return_coefficient_of_variation': return_cv,
            'is_consistent': (
                abs(degradation) < 30 and  # Less than 30% degradation
                max_consecutive_failures <= 2 and  # Max 2 consecutive failures
                sharpe_cv < 50  # Stable Sharpe ratio
            )
        }
        
        logger.info(f"✓ Consistency Analysis:")
        logger.info(f"  Performance Degradation: {degradation:+.1f}%")
        logger.info(f"  Max Consecutive Failures: {max_consecutive_failures}")
        logger.info(f"  Sharpe CV: {sharpe_cv:.1f}%")
        logger.info(f"  Is Consistent: {consistency['is_consistent']}")
        
        return consistency
    
    def get_results_dataframe(self) -> pd.DataFrame:
        """
        Get walk-forward results as DataFrame.
        
        Returns:
            DataFrame with window results
        """
        if not self.windows:
            return pd.DataFrame()
        
        results = []
        for window in self.windows:
            if window.metrics:
                results.append({
                    'window_id': window.window_id,
                    'start_date': window.start_date,
                    'end_date': window.end_date,
                    'window_type': window.window_type,
                    **window.metrics['overview'],
                    **window.metrics['risk_adjusted'],
                    **window.metrics['trade_quality']
                })
        
        return pd.DataFrame(results)
    
    def generate_validation_report(self) -> Dict:
        """
        Generate comprehensive validation report.
        
        Returns:
            Validation report dictionary
        """
        if not self.aggregate_metrics:
            return {'error': 'No test results available'}
        
        report = {
            'summary': {
                'total_windows_tested': self.aggregate_metrics['total_windows'],
                'windows_passing': self.aggregate_metrics['windows_passing_criteria'],
                'overall_pass_rate': self.aggregate_metrics['pass_rate'],
                'is_strategy_validated': self.aggregate_metrics['pass_rate'] >= 70.0
            },
            'performance': {
                'avg_sharpe': self.aggregate_metrics['avg_sharpe'],
                'sharpe_stability': f"±{self.aggregate_metrics['std_sharpe']:.2f}",
                'avg_return': self.aggregate_metrics['avg_return'],
                'worst_drawdown': self.aggregate_metrics['worst_drawdown']
            },
            'recommendation': self._generate_recommendation()
        }
        
        return report
    
    def _generate_recommendation(self) -> str:
        """Generate trading recommendation based on validation results."""
        if not self.aggregate_metrics:
            return "Insufficient data for recommendation"
        
        pass_rate = self.aggregate_metrics['pass_rate']
        avg_sharpe = self.aggregate_metrics['avg_sharpe']
        
        if pass_rate >= 80 and avg_sharpe >= PerformanceMetrics.TARGET_SHARPE:
            return "✅ APPROVED: Strategy shows strong and consistent performance. Ready for live trading with small position sizes."
        elif pass_rate >= 60 and avg_sharpe >= 1.0:
            return "⚠️ CONDITIONAL: Strategy shows promise but needs monitoring. Consider paper trading first."
        else:
            return "❌ NOT READY: Strategy fails validation criteria. Requires significant refinement before live trading."


# Global instance
walk_forward_validator = WalkForwardValidator()
