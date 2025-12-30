"""Composite scoring and ranking logic."""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from scipy import stats
from loguru import logger

from .config import scan_config


class Scorer:
    """Calculate composite scores from normalized factors."""
    
    @staticmethod
    def calculate_z_scores(factors_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculate cross-sectional z-scores for all factors.
        
        Args:
            factors_list: List of factor dictionaries from multiple stocks
        
        Returns:
            List of factors with added z-score fields
        """
        if not factors_list:
            return []
        
        # Convert to DataFrame for easier computation
        df = pd.DataFrame(factors_list)
        
        # Enhanced momentum composite: exponential + Sharpe + consistency
        df['momentum_raw'] = (
            df['momentum_exp'].fillna(0) * 0.5 +  # Exponentially weighted momentum
            df['sharpe_momentum'].fillna(0) * 0.3 +  # Risk-adjusted momentum
            df['momentum_consistency'].fillna(50) * 0.02  # Consistency (scaled from 0-100)
        )
        
        # Enhanced volume composite: ratio + correlation + z-score spike
        df['volume_raw'] = (
            df['volume_ratio'].fillna(1.0) * 0.4 +
            df['volume_price_corr'].fillna(0) * 0.3 +
            df['volume_zscore'].fillna(0) * 0.3
        )
        
        # Volatility composite (inverse - lower is better, but consider regime)
        df['volatility_raw'] = (
            df['volatility_20d'].fillna(df['volatility_20d'].median()) * 0.7 +
            df['vol_regime'].fillna(1.0) * 10  # Regime adds weight if expanding
        )
        
        # Calculate z-scores
        df['z_momentum'] = stats.zscore(df['momentum_raw'].fillna(0))
        df['z_volume'] = stats.zscore(df['volume_raw'].fillna(1))
        df['z_volatility'] = stats.zscore(df['volatility_raw'].fillna(df['volatility_raw'].median()))
        
        # Handle NaN/inf in z-scores
        for col in ['z_momentum', 'z_volume', 'z_volatility']:
            df[col] = df[col].replace([np.inf, -np.inf], 0).fillna(0)
        
        return df.to_dict('records')
    
    @staticmethod
    def calculate_composite_score(factors: Dict[str, Any]) -> float:
        """
        Calculate weighted composite score from z-scores.
        
        Formula:
        score = w_momentum * z_momentum + 
                w_volume * z_volume + 
                w_volatility * (-z_volatility)
        
        Higher score = better opportunity
        """
        weights = scan_config.FACTOR_WEIGHTS
        
        score = (
            weights['momentum'] * factors.get('z_momentum', 0) +
            weights['volume'] * factors.get('z_volume', 0) +
            weights['volatility'] * (-factors.get('z_volatility', 0))  # Inverse
        )
        
        return round(score, 4)
    
    @staticmethod
    def rank_stocks(factors_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank stocks by composite score.
        
        Args:
            factors_list: List of factor dictionaries
        
        Returns:
            Sorted list with composite scores and ranks
        """
        # Calculate z-scores
        factors_with_z = Scorer.calculate_z_scores(factors_list)
        
        # Calculate composite scores
        for factors in factors_with_z:
            factors['composite_score'] = Scorer.calculate_composite_score(factors)
        
        # Sort by composite score (descending)
        ranked = sorted(factors_with_z, key=lambda x: x['composite_score'], reverse=True)
        
        # Add rank
        for i, factors in enumerate(ranked, 1):
            factors['rank'] = i
        
        return ranked
    
    @staticmethod
    def select_top_n(ranked_factors: List[Dict[str, Any]], n: int = None) -> List[Dict[str, Any]]:
        """
        Select top N stocks from ranked list.
        
        Args:
            ranked_factors: List of ranked factor dictionaries
            n: Number of stocks to select (default from config)
        
        Returns:
            Top N stocks
        """
        if n is None:
            n = scan_config.TOP_N_SIGNALS
        
        return ranked_factors[:n]
    
    @staticmethod
    def format_signal(factors: Dict[str, Any], include_detailed: bool = True) -> Dict[str, Any]:
        """
        Format factor data into a clean signal output.
        
        Args:
            factors: Factor dictionary
            include_detailed: Whether to include all factor details
        
        Returns:
            Formatted signal dictionary
        """
        signal = {
            'ticker': factors['ticker'],
            'rank': factors.get('rank'),
            'composite_score': factors.get('composite_score'),
            'price': factors.get('price'),
            'volume': factors.get('volume'),
        }
        
        if include_detailed:
            signal['factors'] = {
                'momentum': {
                    'return_5d': factors.get('return_5d'),
                    'return_10d': factors.get('return_10d'),
                    'return_20d': factors.get('return_20d'),
                    'rsi_14': factors.get('rsi_14'),
                    'ema_cross': factors.get('ema_cross'),
                    'z_score': factors.get('z_momentum'),
                    # Enhanced momentum metrics
                    'momentum_exp': factors.get('momentum_exp'),
                    'sharpe_momentum': factors.get('sharpe_momentum'),
                    'momentum_consistency': factors.get('momentum_consistency'),
                    'momentum_accel': factors.get('momentum_accel')
                },
                'volatility': {
                    'volatility_20d': factors.get('volatility_20d'),
                    'atr_14': factors.get('atr_14'),
                    'atr_pct': factors.get('atr_pct'),
                    'z_score': factors.get('z_volatility'),
                    # Enhanced volatility metrics
                    'vol_regime': factors.get('vol_regime'),
                    'vol_trend': factors.get('vol_trend')
                },
                'volume': {
                    'volume_20d_avg': factors.get('volume_20d_avg'),
                    'volume_ratio': factors.get('volume_ratio'),
                    'dollar_volume': factors.get('dollar_volume'),
                    'z_score': factors.get('z_volume'),
                    # Enhanced volume metrics
                    'volume_price_corr': factors.get('volume_price_corr'),
                    'volume_zscore': factors.get('volume_zscore'),
                    'obv_trend': factors.get('obv_trend')
                },
                'technical': {
                    'ema_9': factors.get('ema_9'),
                    'ema_21': factors.get('ema_21'),
                    'ema_50': factors.get('ema_50'),
                    'macd': factors.get('macd'),
                    'macd_signal': factors.get('macd_signal')
                }
            }
        
        return signal
    
    @staticmethod
    def compare_signals(old_signals: List[Dict], new_signals: List[Dict]) -> Dict[str, Any]:
        """
        Compare two sets of signals (e.g., 9am vs 10am scan).
        
        Returns:
            Dictionary with changes, warnings, and recommendations
        """
        old_tickers = {s['ticker']: s for s in old_signals}
        new_tickers = {s['ticker']: s for s in new_signals}
        
        changes = {
            'dropped': [],
            'added': [],
            'score_changes': [],
            'price_moves': []
        }
        
        # Find dropped tickers
        for ticker in old_tickers:
            if ticker not in new_tickers:
                changes['dropped'].append({
                    'ticker': ticker,
                    'old_rank': old_tickers[ticker].get('rank'),
                    'old_score': old_tickers[ticker].get('composite_score')
                })
        
        # Find added tickers
        for ticker in new_tickers:
            if ticker not in old_tickers:
                changes['added'].append({
                    'ticker': ticker,
                    'new_rank': new_tickers[ticker].get('rank'),
                    'new_score': new_tickers[ticker].get('composite_score')
                })
        
        # Compare common tickers
        for ticker in set(old_tickers) & set(new_tickers):
            old_sig = old_tickers[ticker]
            new_sig = new_tickers[ticker]
            
            # Score changes
            old_score = old_sig.get('composite_score', 0)
            new_score = new_sig.get('composite_score', 0)
            score_change = new_score - old_score
            
            if abs(score_change) > 0.5:  # Significant change threshold
                changes['score_changes'].append({
                    'ticker': ticker,
                    'old_score': old_score,
                    'new_score': new_score,
                    'change': score_change
                })
            
            # Price moves
            old_price = old_sig.get('price', 0)
            new_price = new_sig.get('price', 0)
            if old_price > 0:
                price_change_pct = ((new_price / old_price) - 1) * 100
                if abs(price_change_pct) > 2:  # >2% move
                    changes['price_moves'].append({
                        'ticker': ticker,
                        'old_price': old_price,
                        'new_price': new_price,
                        'change_pct': price_change_pct
                    })
        
        return changes


# Global scorer instance
scorer = Scorer()
