"""Risk management and position sizing calculations."""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from loguru import logger

from .config import scan_config


class RiskManager:
    """Calculate position sizes, stop losses, and risk metrics."""
    
    # Risk management parameters
    MAX_POSITION_SIZE = 0.10  # Max 10% of portfolio per position
    MAX_PORTFOLIO_RISK = 0.02  # Max 2% portfolio risk per trade
    MAX_SECTOR_EXPOSURE = 0.30  # Max 30% in any sector
    STOP_LOSS_ATR_MULTIPLE = 2.0  # Stop loss at 2x ATR below entry
    MIN_RISK_REWARD = 2.0  # Minimum 2:1 reward-to-risk ratio
    
    def __init__(self, portfolio_value: float = 100000):
        """
        Initialize risk manager.
        
        Args:
            portfolio_value: Total portfolio value in dollars
        """
        self.portfolio_value = portfolio_value
    
    def calculate_position_size(
        self, 
        price: float,
        atr: float,
        win_rate: float = 0.5,
        avg_win_loss_ratio: float = 2.0,
        composite_score: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculate optimal position size using simplified Kelly criterion.
        
        Args:
            price: Current stock price
            atr: Average True Range (volatility measure)
            win_rate: Historical win rate (default 50%)
            avg_win_loss_ratio: Average win/loss ratio (default 2:1)
            composite_score: Composite score from factor analysis
            
        Returns:
            Dictionary with position sizing details
        """
        try:
            # Kelly fraction: f = (p*b - q) / b
            # where p = win rate, q = 1-p, b = win/loss ratio
            p = win_rate
            q = 1 - p
            b = avg_win_loss_ratio
            
            kelly_fraction = (p * b - q) / b if b > 0 else 0
            
            # Cap Kelly at 10% and apply half-Kelly for safety
            kelly_fraction = max(0, min(kelly_fraction, self.MAX_POSITION_SIZE))
            half_kelly = kelly_fraction * 0.5
            
            # Adjust by composite score quality (higher score = allow larger position)
            # Score is typically -3 to +3, normalize to 0.5 to 1.0 multiplier
            score_adjustment = 0.5 + (min(max(composite_score, -3), 3) / 6) * 0.5
            
            adjusted_fraction = half_kelly * score_adjustment
            
            # Calculate position value and shares
            position_value = self.portfolio_value * adjusted_fraction
            shares = int(position_value / price)
            actual_position_value = shares * price
            actual_fraction = actual_position_value / self.portfolio_value
            
            return {
                'kelly_fraction': round(kelly_fraction, 4),
                'half_kelly': round(half_kelly, 4),
                'adjusted_fraction': round(adjusted_fraction, 4),
                'position_value': round(actual_position_value, 2),
                'shares': shares,
                'actual_fraction': round(actual_fraction, 4),
                'score_adjustment': round(score_adjustment, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return {
                'kelly_fraction': 0,
                'half_kelly': 0,
                'adjusted_fraction': 0,
                'position_value': 0,
                'shares': 0,
                'actual_fraction': 0,
                'score_adjustment': 1.0
            }
    
    def calculate_stops(
        self,
        entry_price: float,
        atr: float,
        direction: str = 'long'
    ) -> Dict[str, float]:
        """
        Calculate stop loss and take profit levels using ATR.
        
        Args:
            entry_price: Entry price for the position
            atr: Average True Range
            direction: 'long' or 'short' (default 'long')
            
        Returns:
            Dictionary with stop and target levels
        """
        try:
            if direction.lower() == 'long':
                # Stop loss: Entry - (2 * ATR)
                stop_loss = entry_price - (self.STOP_LOSS_ATR_MULTIPLE * atr)
                
                # Risk amount per share
                risk_per_share = entry_price - stop_loss
                
                # Take profit: Entry + (2 * risk) for 2:1 reward/risk
                take_profit = entry_price + (self.MIN_RISK_REWARD * risk_per_share)
                
            else:  # short
                # Stop loss: Entry + (2 * ATR)
                stop_loss = entry_price + (self.STOP_LOSS_ATR_MULTIPLE * atr)
                
                # Risk amount per share
                risk_per_share = stop_loss - entry_price
                
                # Take profit: Entry - (2 * risk)
                take_profit = entry_price - (self.MIN_RISK_REWARD * risk_per_share)
            
            # Stop loss percentage
            stop_loss_pct = abs((stop_loss - entry_price) / entry_price) * 100
            
            # Take profit percentage
            take_profit_pct = abs((take_profit - entry_price) / entry_price) * 100
            
            return {
                'stop_loss': round(stop_loss, 2),
                'stop_loss_pct': round(stop_loss_pct, 2),
                'take_profit': round(take_profit, 2),
                'take_profit_pct': round(take_profit_pct, 2),
                'risk_per_share': round(risk_per_share, 2),
                'reward_risk_ratio': self.MIN_RISK_REWARD
            }
            
        except Exception as e:
            logger.error(f"Error calculating stops: {e}")
            return {
                'stop_loss': 0,
                'stop_loss_pct': 0,
                'take_profit': 0,
                'take_profit_pct': 0,
                'risk_per_share': 0,
                'reward_risk_ratio': 0
            }
    
    def calculate_risk_amount(
        self,
        shares: int,
        entry_price: float,
        stop_loss: float
    ) -> Dict[str, float]:
        """
        Calculate total dollar risk for the position.
        
        Args:
            shares: Number of shares
            entry_price: Entry price
            stop_loss: Stop loss price
            
        Returns:
            Dictionary with risk amounts
        """
        try:
            risk_per_share = abs(entry_price - stop_loss)
            total_risk = shares * risk_per_share
            portfolio_risk_pct = (total_risk / self.portfolio_value) * 100
            
            return {
                'risk_per_share': round(risk_per_share, 2),
                'total_risk': round(total_risk, 2),
                'portfolio_risk_pct': round(portfolio_risk_pct, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk amount: {e}")
            return {
                'risk_per_share': 0,
                'total_risk': 0,
                'portfolio_risk_pct': 0
            }
    
    def validate_trade(
        self,
        position_value: float,
        total_risk: float,
        sector_exposure: float = 0.0
    ) -> Dict[str, Any]:
        """
        Validate if trade meets risk management criteria.
        
        Args:
            position_value: Dollar value of position
            total_risk: Total dollar risk
            sector_exposure: Current sector exposure as fraction
            
        Returns:
            Dictionary with validation results
        """
        try:
            position_fraction = position_value / self.portfolio_value
            risk_fraction = total_risk / self.portfolio_value
            
            checks = {
                'position_size_ok': position_fraction <= self.MAX_POSITION_SIZE,
                'portfolio_risk_ok': risk_fraction <= self.MAX_PORTFOLIO_RISK,
                'sector_exposure_ok': sector_exposure <= self.MAX_SECTOR_EXPOSURE,
            }
            
            all_passed = all(checks.values())
            
            warnings = []
            if not checks['position_size_ok']:
                warnings.append(f"Position size {position_fraction:.1%} exceeds max {self.MAX_POSITION_SIZE:.1%}")
            if not checks['portfolio_risk_ok']:
                warnings.append(f"Portfolio risk {risk_fraction:.1%} exceeds max {self.MAX_PORTFOLIO_RISK:.1%}")
            if not checks['sector_exposure_ok']:
                warnings.append(f"Sector exposure {sector_exposure:.1%} exceeds max {self.MAX_SECTOR_EXPOSURE:.1%}")
            
            return {
                'valid': all_passed,
                'checks': checks,
                'warnings': warnings,
                'position_fraction': round(position_fraction, 4),
                'risk_fraction': round(risk_fraction, 4)
            }
            
        except Exception as e:
            logger.error(f"Error validating trade: {e}")
            return {
                'valid': False,
                'checks': {},
                'warnings': [f"Validation error: {e}"],
                'position_fraction': 0,
                'risk_fraction': 0
            }
    
    def calculate_quality_score(
        self,
        factors: Dict[str, Any]
    ) -> float:
        """
        Calculate a quality score (0-100) based on various factors.
        
        Args:
            factors: Dictionary of calculated factors
            
        Returns:
            Quality score from 0 to 100
        """
        try:
            score = 50.0  # Start at neutral
            
            # Momentum quality (+/- 20 points)
            momentum_consistency = factors.get('momentum_consistency')
            if momentum_consistency is not None:
                score += (momentum_consistency - 50) * 0.4
            
            # Volume quality (+/- 15 points)
            volume_corr = factors.get('volume_price_corr')
            if volume_corr is not None:
                score += volume_corr * 15
            
            # Volatility regime (+/- 10 points)
            vol_regime = factors.get('vol_regime')
            if vol_regime is not None:
                if vol_regime < 1.0:  # Low volatility is better
                    score += (1.0 - vol_regime) * 10
                else:
                    score -= (vol_regime - 1.0) * 10
            
            # Sharpe momentum (+/- 5 points)
            sharpe_mom = factors.get('sharpe_momentum')
            if sharpe_mom is not None:
                score += sharpe_mom * 5
            
            # Clamp to 0-100
            score = max(0, min(100, score))
            
            return round(score, 1)
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {e}")
            return 50.0
    
    def generate_trade_plan(
        self,
        ticker: str,
        price: float,
        atr: float,
        composite_score: float,
        factors: Dict[str, Any],
        direction: str = 'long'
    ) -> Dict[str, Any]:
        """
        Generate complete trade plan with position sizing and risk metrics.
        
        Args:
            ticker: Stock ticker
            price: Current price
            atr: Average True Range
            composite_score: Composite factor score
            factors: All calculated factors
            direction: Trade direction
            
        Returns:
            Complete trade plan dictionary
        """
        try:
            # Calculate position size
            position_sizing = self.calculate_position_size(
                price=price,
                atr=atr,
                composite_score=composite_score
            )
            
            # Calculate stop loss and take profit
            stops = self.calculate_stops(
                entry_price=price,
                atr=atr,
                direction=direction
            )
            
            # Calculate risk amounts
            risk_amounts = self.calculate_risk_amount(
                shares=position_sizing['shares'],
                entry_price=price,
                stop_loss=stops['stop_loss']
            )
            
            # Calculate quality score
            quality_score = self.calculate_quality_score(factors)
            
            # Validate trade
            validation = self.validate_trade(
                position_value=position_sizing['position_value'],
                total_risk=risk_amounts['total_risk']
            )
            
            # Compile trade plan
            trade_plan = {
                'ticker': ticker,
                'direction': direction,
                'entry_price': round(price, 2),
                'composite_score': round(composite_score, 2),
                'quality_score': quality_score,
                
                # Position sizing
                'shares': position_sizing['shares'],
                'position_value': position_sizing['position_value'],
                'position_pct': position_sizing['actual_fraction'] * 100,
                
                # Risk levels
                'stop_loss': stops['stop_loss'],
                'stop_loss_pct': stops['stop_loss_pct'],
                'take_profit': stops['take_profit'],
                'take_profit_pct': stops['take_profit_pct'],
                
                # Risk metrics
                'risk_per_share': risk_amounts['risk_per_share'],
                'total_risk': risk_amounts['total_risk'],
                'portfolio_risk_pct': risk_amounts['portfolio_risk_pct'],
                'reward_risk_ratio': stops['reward_risk_ratio'],
                
                # Validation
                'valid': validation['valid'],
                'warnings': validation['warnings']
            }
            
            return trade_plan
            
        except Exception as e:
            logger.error(f"Error generating trade plan for {ticker}: {e}")
            return {
                'ticker': ticker,
                'error': str(e),
                'valid': False
            }


# Global risk manager instance (default $100k portfolio)
risk_manager = RiskManager(portfolio_value=100000)
