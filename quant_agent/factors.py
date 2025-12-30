"""Technical factor calculations using pandas-ta."""

import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, Any
from loguru import logger

from .config import scan_config


class FactorCalculator:
    """Calculate technical factors for stock analysis."""
    
    @staticmethod
    def calculate_returns(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate multi-period returns."""
        close = df['Close']
        factors = {}
        
        for window in scan_config.RETURN_WINDOWS:
            if len(close) >= window + 1:
                ret = (close.iloc[-1] / close.iloc[-window-1] - 1) * 100
                factors[f'return_{window}d'] = ret
            else:
                factors[f'return_{window}d'] = None
        
        return factors
    
    @staticmethod
    def calculate_advanced_momentum(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate advanced momentum metrics with exponential weighting and risk adjustment."""
        factors = {}
        close = df['Close']
        
        # Exponentially weighted momentum (recent returns weighted more heavily)
        if len(close) >= 21:
            ret_1d = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0
            ret_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
            ret_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0
            
            # Exponential weights: 1d=50%, 5d=30%, 20d=20%
            factors['momentum_exp'] = ret_1d * 0.5 + ret_5d * 0.3 + ret_20d * 0.2
        else:
            factors['momentum_exp'] = None
        
        # Sharpe-adjusted returns (return per unit of volatility)
        if len(close) >= 21:
            returns = close.pct_change()
            ret_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100
            vol_20d = returns.iloc[-20:].std() * np.sqrt(252) * 100
            
            if vol_20d and vol_20d > 0:
                factors['sharpe_momentum'] = ret_20d / vol_20d
            else:
                factors['sharpe_momentum'] = None
        else:
            factors['sharpe_momentum'] = None
        
        # Momentum consistency (% of positive days in last 20 days)
        if len(close) >= 21:
            returns = close.pct_change().iloc[-20:]
            factors['momentum_consistency'] = (returns > 0).sum() / len(returns) * 100
        else:
            factors['momentum_consistency'] = None
        
        # Momentum acceleration (comparing recent vs older momentum)
        if len(close) >= 21:
            ret_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
            ret_15_10d = (close.iloc[-11] / close.iloc[-16] - 1) * 100 if len(close) >= 16 else 0
            factors['momentum_accel'] = ret_5d - ret_15_10d
        else:
            factors['momentum_accel'] = None
        
        return factors
    
    @staticmethod
    def calculate_volume_quality(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volume quality metrics including spike detection."""
        factors = {}
        
        volume = df['Volume']
        close = df['Close']
        
        if len(volume) >= 21:
            # Volume-price correlation (strong correlation = quality move)
            returns = close.pct_change().iloc[-20:]
            vol_change = volume.pct_change().iloc[-20:]
            
            # Filter out NaN values
            valid_mask = ~(returns.isna() | vol_change.isna())
            if valid_mask.sum() >= 10:
                correlation = returns[valid_mask].corr(vol_change[valid_mask])
                factors['volume_price_corr'] = correlation if not np.isnan(correlation) else 0
            else:
                factors['volume_price_corr'] = 0
            
            # Volume z-score (spike detection)
            vol_mean = volume.iloc[-20:].mean()
            vol_std = volume.iloc[-20:].std()
            
            if vol_std and vol_std > 0:
                current_vol = volume.iloc[-1]
                factors['volume_zscore'] = (current_vol - vol_mean) / vol_std
            else:
                factors['volume_zscore'] = 0
            
            # OBV trend (On-Balance Volume)
            obv = ta.obv(close, volume)
            if obv is not None and not obv.empty and len(obv) >= 11:
                obv_current = obv.iloc[-1]
                obv_10d_ago = obv.iloc[-11]
                factors['obv_trend'] = ((obv_current / obv_10d_ago) - 1) * 100 if obv_10d_ago != 0 else 0
            else:
                factors['obv_trend'] = 0
        else:
            factors['volume_price_corr'] = 0
            factors['volume_zscore'] = 0
            factors['obv_trend'] = 0
        
        return factors
    
    @staticmethod
    def calculate_volatility_regime(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volatility regime and trend detection."""
        factors = {}
        
        if len(df) >= 21:
            returns = df['Close'].pct_change()
            
            # Short-term vs long-term volatility ratio
            vol_5d = returns.iloc[-5:].std() * np.sqrt(252) * 100 if len(returns) >= 5 else None
            vol_20d = returns.iloc[-20:].std() * np.sqrt(252) * 100 if len(returns) >= 20 else None
            
            if vol_5d and vol_20d and vol_20d > 0:
                factors['vol_regime'] = vol_5d / vol_20d
            else:
                factors['vol_regime'] = 1.0
            
            # Volatility trend (increasing or decreasing)
            if len(returns) >= 21:
                vol_10d_recent = returns.iloc[-10:].std() * np.sqrt(252) * 100
                vol_10d_old = returns.iloc[-20:-10].std() * np.sqrt(252) * 100
                
                if vol_10d_old and vol_10d_old > 0:
                    factors['vol_trend'] = ((vol_10d_recent / vol_10d_old) - 1) * 100
                else:
                    factors['vol_trend'] = 0
            else:
                factors['vol_trend'] = 0
        else:
            factors['vol_regime'] = 1.0
            factors['vol_trend'] = 0
        
        return factors
    
    @staticmethod
    def calculate_momentum_indicators(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate momentum indicators."""
        factors = {}
        
        # RSI
        rsi = ta.rsi(df['Close'], length=scan_config.RSI_PERIOD)
        if rsi is not None and not rsi.empty:
            factors['rsi_14'] = float(rsi.iloc[-1])
        else:
            factors['rsi_14'] = None
        
        # EMAs
        ema_fast = ta.ema(df['Close'], length=scan_config.EMA_FAST)
        ema_slow = ta.ema(df['Close'], length=scan_config.EMA_SLOW)
        ema_trend = ta.ema(df['Close'], length=scan_config.EMA_TREND)
        
        if ema_fast is not None and not ema_fast.empty:
            factors['ema_9'] = float(ema_fast.iloc[-1])
        else:
            factors['ema_9'] = None
            
        if ema_slow is not None and not ema_slow.empty:
            factors['ema_21'] = float(ema_slow.iloc[-1])
        else:
            factors['ema_21'] = None
            
        if ema_trend is not None and not ema_trend.empty:
            factors['ema_50'] = float(ema_trend.iloc[-1])
        else:
            factors['ema_50'] = None
        
        # EMA crossover strength
        if factors['ema_9'] and factors['ema_21']:
            factors['ema_cross'] = ((factors['ema_9'] / factors['ema_21']) - 1) * 100
        else:
            factors['ema_cross'] = None
        
        # MACD
        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            factors['macd'] = float(macd['MACD_12_26_9'].iloc[-1])
            factors['macd_signal'] = float(macd['MACDs_12_26_9'].iloc[-1])
            factors['macd_hist'] = float(macd['MACDh_12_26_9'].iloc[-1])
        else:
            factors['macd'] = None
            factors['macd_signal'] = None
            factors['macd_hist'] = None
        
        return factors
    
    @staticmethod
    def calculate_volatility(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volatility metrics."""
        factors = {}
        
        # Historical volatility (annualized)
        returns = df['Close'].pct_change()
        if len(returns) >= scan_config.VOLATILITY_WINDOW:
            vol = returns.iloc[-scan_config.VOLATILITY_WINDOW:].std() * np.sqrt(252) * 100
            factors['volatility_20d'] = vol
        else:
            factors['volatility_20d'] = None
        
        # ATR
        atr = ta.atr(df['High'], df['Low'], df['Close'], length=scan_config.ATR_PERIOD)
        if atr is not None and not atr.empty:
            atr_value = float(atr.iloc[-1])
            factors['atr_14'] = atr_value
            # ATR as percentage of price
            factors['atr_pct'] = (atr_value / df['Close'].iloc[-1]) * 100
        else:
            factors['atr_14'] = None
            factors['atr_pct'] = None
        
        return factors
    
    @staticmethod
    def calculate_volume_metrics(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volume and liquidity metrics."""
        factors = {}
        
        volume = df['Volume']
        
        # Average volume
        if len(volume) >= scan_config.VOLUME_WINDOW:
            avg_vol = volume.iloc[-scan_config.VOLUME_WINDOW:].mean()
            factors['volume_20d_avg'] = int(avg_vol)
            
            # Current vs average volume ratio
            current_vol = volume.iloc[-1]
            factors['volume_ratio'] = current_vol / avg_vol if avg_vol > 0 else None
            
            # Dollar volume
            factors['dollar_volume'] = int(current_vol * df['Close'].iloc[-1])
        else:
            factors['volume_20d_avg'] = None
            factors['volume_ratio'] = None
            factors['dollar_volume'] = None
        
        return factors
    
    @staticmethod
    def calculate_all_factors(df: pd.DataFrame, ticker: str) -> Dict[str, Any]:
        """Calculate all technical factors for a ticker."""
        try:
            factors = {'ticker': ticker}
            
            # Basic price info
            factors['price'] = float(df['Close'].iloc[-1])
            factors['volume'] = int(df['Volume'].iloc[-1])
            
            # Calculate factor groups
            factors.update(FactorCalculator.calculate_returns(df))
            factors.update(FactorCalculator.calculate_momentum_indicators(df))
            factors.update(FactorCalculator.calculate_volatility(df))
            factors.update(FactorCalculator.calculate_volume_metrics(df))
            
            # Calculate advanced factors
            factors.update(FactorCalculator.calculate_advanced_momentum(df))
            factors.update(FactorCalculator.calculate_volume_quality(df))
            factors.update(FactorCalculator.calculate_volatility_regime(df))
            
            return factors
            
        except Exception as e:
            logger.error(f"Error calculating factors for {ticker}: {e}")
            return None
    
    @staticmethod
    def apply_filters(factors: Dict[str, Any]) -> bool:
        """
        Apply basic filters to determine if stock passes screening.
        
        Returns:
            True if stock passes all filters, False otherwise
        """
        # Price filter
        if factors.get('price', 0) < scan_config.MIN_PRICE:
            return False
        
        # Volume filter
        avg_vol = factors.get('volume_20d_avg', 0)
        if avg_vol and avg_vol < scan_config.MIN_AVG_VOLUME:
            return False
        
        # Volatility filter (too high)
        vol = factors.get('volatility_20d')
        if vol and vol > scan_config.MAX_VOLATILITY * 100:
            return False
        
        # Data quality - must have key factors
        required = ['return_10d', 'rsi_14', 'volatility_20d', 'volume_ratio']
        if any(factors.get(f) is None for f in required):
            return False
        
        return True


# Global factor calculator instance
factor_calculator = FactorCalculator()
