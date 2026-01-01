"""Market regime detection for risk management."""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from datetime import datetime, timedelta
from loguru import logger

from .questrade_loader import QuestradeDataLoader


class MarketRegimeDetector:
    """Detect market regime (bull/bear/neutral) and volatility conditions."""
    
    # Regime thresholds
    BULL_TREND_THRESHOLD = 0.02  # 2% above 50 EMA
    BEAR_TREND_THRESHOLD = -0.02  # 2% below 50 EMA
    VIX_LOW = 15
    VIX_MEDIUM = 25
    VIX_HIGH = 30
    
    def __init__(self):
        self._data_loader = None
        self._spy_data = None
        self._vix_data = None
        self._last_update = None
    
    @property
    def data_loader(self):
        """Lazy initialization of QuestradeDataLoader."""
        if self._data_loader is None:
            self._data_loader = QuestradeDataLoader()
        return self._data_loader
    
    def update_market_data(self, force_refresh: bool = False) -> bool:
        """
        Update SPY and VIX data.
        
        Args:
            force_refresh: Force download new data
            
        Returns:
            Success status
        """
        try:
            # Update if not loaded or older than 1 hour or forced
            if (force_refresh or 
                self._spy_data is None or 
                self._last_update is None or
                datetime.now() - self._last_update > timedelta(hours=1)):
                
                # Download SPY data (S&P 500 ETF as market proxy)
                self._spy_data = self.data_loader.download_ticker(
                    'SPY',
                    period='90d',
                    use_cache=not force_refresh
                )
                
                if self._spy_data is None or len(self._spy_data) == 0:
                    logger.error("Failed to download SPY data")
                    return False
                
                # Note: VIX data would require separate API or manual tracking
                # For now, we'll estimate volatility from SPY
                self._last_update = datetime.now()
                logger.info(f"✓ Market data updated ({len(self._spy_data)} days)")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to update market data: {e}")
            return False
    
    def get_spy_trend(self) -> Tuple[str, float]:
        """
        Determine SPY trend direction.
        
        Returns:
            Tuple of (trend, strength) where:
            - trend: 'uptrend', 'downtrend', or 'sideways'
            - strength: percentage deviation from 50 EMA
        """
        if self._spy_data is None or len(self._spy_data) < 50:
            return 'unknown', 0.0
        
        try:
            close = self._spy_data['Close']
            current_price = close.iloc[-1]
            
            # Calculate 50-day EMA
            ema_50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
            
            # Calculate deviation
            deviation = (current_price / ema_50 - 1)
            
            # Determine trend
            if deviation > self.BULL_TREND_THRESHOLD:
                trend = 'uptrend'
            elif deviation < self.BEAR_TREND_THRESHOLD:
                trend = 'downtrend'
            else:
                trend = 'sideways'
            
            return trend, round(deviation * 100, 2)
            
        except Exception as e:
            logger.error(f"Error calculating SPY trend: {e}")
            return 'unknown', 0.0
    
    def get_volatility_regime(self) -> Tuple[str, float]:
        """
        Determine current volatility regime.
        
        Returns:
            Tuple of (regime, value) where:
            - regime: 'low', 'medium', 'high', or 'extreme'
            - value: estimated VIX-equivalent from SPY
        """
        if self._spy_data is None or len(self._spy_data) < 20:
            return 'unknown', 0.0
        
        try:
            # Calculate realized volatility from SPY (annualized)
            returns = self._spy_data['Close'].pct_change()
            realized_vol = returns.iloc[-20:].std() * np.sqrt(252) * 100
            
            # Classify regime
            if realized_vol < self.VIX_LOW:
                regime = 'low'
            elif realized_vol < self.VIX_MEDIUM:
                regime = 'medium'
            elif realized_vol < self.VIX_HIGH:
                regime = 'high'
            else:
                regime = 'extreme'
            
            return regime, round(realized_vol, 2)
            
        except Exception as e:
            logger.error(f"Error calculating volatility regime: {e}")
            return 'unknown', 0.0
    
    def get_market_regime(self) -> Dict[str, any]:
        """
        Get complete market regime assessment.
        
        Returns:
            Dictionary with regime information
        """
        # Update data if needed
        self.update_market_data()
        
        trend, trend_strength = self.get_spy_trend()
        vol_regime, vol_value = self.get_volatility_regime()
        
        # Determine overall regime
        if trend == 'uptrend' and vol_regime in ['low', 'medium']:
            overall_regime = 'bull'
            risk_level = 'low'
        elif trend == 'downtrend' or vol_regime == 'extreme':
            overall_regime = 'bear'
            risk_level = 'high'
        elif vol_regime == 'high':
            overall_regime = 'volatile'
            risk_level = 'medium'
        else:
            overall_regime = 'neutral'
            risk_level = 'medium'
        
        # Calculate position size multiplier
        if overall_regime == 'bull':
            position_multiplier = 1.0
        elif overall_regime == 'neutral':
            position_multiplier = 0.7
        elif overall_regime == 'volatile':
            position_multiplier = 0.5
        else:  # bear
            position_multiplier = 0.3
        
        return {
            'overall_regime': overall_regime,
            'trend': trend,
            'trend_strength': trend_strength,
            'volatility_regime': vol_regime,
            'volatility_value': vol_value,
            'risk_level': risk_level,
            'position_multiplier': position_multiplier,
            'should_trade': overall_regime != 'bear' or position_multiplier > 0,
            'timestamp': datetime.now().isoformat()
        }
    
    def should_trade_today(self) -> Tuple[bool, str]:
        """
        Determine if we should trade today based on market conditions.
        
        Returns:
            Tuple of (should_trade, reason)
        """
        regime = self.get_market_regime()
        
        # Don't trade in extreme conditions
        if regime['volatility_regime'] == 'extreme':
            return False, "Extreme volatility - market too unstable"
        
        # Don't trade in strong bear market
        if regime['overall_regime'] == 'bear' and regime['trend_strength'] < -5:
            return False, "Strong downtrend - avoid new positions"
        
        # Otherwise OK to trade (with adjusted sizing)
        return True, f"Market regime: {regime['overall_regime']} (position size: {regime['position_multiplier']*100:.0f}%)"
    
    def adjust_position_size(
        self,
        base_position_size: float,
        base_shares: int
    ) -> Tuple[float, int]:
        """
        Adjust position size based on market regime.
        
        Args:
            base_position_size: Base position value
            base_shares: Base number of shares
            
        Returns:
            Tuple of (adjusted_position_size, adjusted_shares)
        """
        regime = self.get_market_regime()
        multiplier = regime['position_multiplier']
        
        adjusted_value = base_position_size * multiplier
        adjusted_shares = int(base_shares * multiplier)
        
        return adjusted_value, adjusted_shares


# Global instance
market_regime_detector = MarketRegimeDetector()
