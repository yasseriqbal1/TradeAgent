"""Portfolio correlation and concentration risk management."""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from loguru import logger


class PortfolioCorrelationManager:
    """Manage portfolio correlation and sector concentration limits."""
    
    # Risk limits
    MAX_CORRELATION = 0.7  # Max correlation between any two positions
    MAX_SECTOR_EXPOSURE = 0.30  # Max 30% in any sector
    MAX_PORTFOLIO_CORRELATION = 0.6  # Max avg correlation to portfolio
    
    # Sector classifications (focused on user's holdings)
    SECTOR_MAP = {
        # Tech/Software
        'NVDA': 'semiconductors',
        'MSFT': 'software',
        'AAPL': 'consumer_tech',
        'GOOGL': 'software',
        
        # Quantum Computing / AI
        'QBTS': 'quantum_computing',
        'QUBT': 'quantum_computing',
        'RGTI': 'quantum_computing',
        'IONQ': 'quantum_computing',
        
        # Defense/Aerospace Tech
        'PLTR': 'defense_tech',
        'LAES': 'defense_tech',
        
        # Cloud/Enterprise Software
        'SNOW': 'cloud_software',
        'MU': 'semiconductors',
    }
    
    def __init__(self):
        self.correlation_cache = {}
        self.last_calculation = None
    
    def calculate_correlation_matrix(
        self,
        returns_data: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix for multiple stocks.
        
        Args:
            returns_data: Dictionary of ticker -> returns Series
            
        Returns:
            Correlation matrix DataFrame
        """
        try:
            # Convert to DataFrame
            returns_df = pd.DataFrame(returns_data)
            
            # Calculate correlation
            corr_matrix = returns_df.corr()
            
            return corr_matrix
            
        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            return pd.DataFrame()
    
    def check_position_correlation(
        self,
        new_ticker: str,
        existing_positions: List[str],
        historical_data: Dict[str, pd.DataFrame],
        lookback_days: int = 60
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Check if new position correlates too highly with existing positions.
        
        Args:
            new_ticker: Ticker to add
            existing_positions: List of current position tickers
            historical_data: Historical OHLCV data
            lookback_days: Days of history to use
            
        Returns:
            Tuple of (is_valid, correlation_dict)
        """
        if not existing_positions:
            return True, {}
        
        try:
            correlations = {}
            
            # Get returns for new ticker
            if new_ticker not in historical_data:
                logger.warning(f"No data for {new_ticker}")
                return True, {}
            
            new_returns = historical_data[new_ticker]['Close'].pct_change().iloc[-lookback_days:]
            
            # Calculate correlation with each existing position
            for existing_ticker in existing_positions:
                if existing_ticker not in historical_data:
                    continue
                
                existing_returns = historical_data[existing_ticker]['Close'].pct_change().iloc[-lookback_days:]
                
                # Align dates
                aligned_new, aligned_existing = new_returns.align(existing_returns, join='inner')
                
                if len(aligned_new) < 20:
                    logger.warning(f"Insufficient overlapping data for {new_ticker} vs {existing_ticker}")
                    continue
                
                # Calculate correlation
                corr = aligned_new.corr(aligned_existing)
                correlations[existing_ticker] = round(corr, 3)
            
            # Check if any correlation exceeds threshold
            max_corr = max(correlations.values()) if correlations else 0
            is_valid = max_corr < self.MAX_CORRELATION
            
            if not is_valid:
                high_corr_tickers = [t for t, c in correlations.items() if c >= self.MAX_CORRELATION]
                logger.warning(
                    f"{new_ticker} has high correlation with {', '.join(high_corr_tickers)} "
                    f"(max: {max_corr:.3f})"
                )
            
            return is_valid, correlations
            
        except Exception as e:
            logger.error(f"Error checking correlation: {e}")
            return True, {}
    
    def calculate_sector_exposure(
        self,
        positions: List[Dict[str, any]]
    ) -> Dict[str, float]:
        """
        Calculate sector exposure percentages.
        
        Args:
            positions: List of position dictionaries with 'ticker' and 'position_value'
            
        Returns:
            Dictionary of sector -> exposure percentage
        """
        try:
            sector_values = {}
            total_value = sum(p.get('position_value', 0) for p in positions)
            
            if total_value == 0:
                return {}
            
            for position in positions:
                ticker = position.get('ticker')
                value = position.get('position_value', 0)
                
                sector = self.SECTOR_MAP.get(ticker, 'unknown')
                sector_values[sector] = sector_values.get(sector, 0) + value
            
            # Convert to percentages
            sector_exposure = {
                sector: round(value / total_value, 3)
                for sector, value in sector_values.items()
            }
            
            return sector_exposure
            
        except Exception as e:
            logger.error(f"Error calculating sector exposure: {e}")
            return {}
    
    def check_sector_limits(
        self,
        new_ticker: str,
        new_position_value: float,
        existing_positions: List[Dict[str, any]],
        portfolio_value: float
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Check if adding new position would violate sector limits.
        
        Args:
            new_ticker: Ticker to add
            new_position_value: Value of new position
            existing_positions: Current positions
            portfolio_value: Total portfolio value
            
        Returns:
            Tuple of (is_valid, sector_exposure_dict)
        """
        try:
            # Add new position to existing
            all_positions = existing_positions + [{
                'ticker': new_ticker,
                'position_value': new_position_value
            }]
            
            # Calculate exposure
            sector_exposure = self.calculate_sector_exposure(all_positions)
            
            # Check limits
            violations = {
                sector: exposure
                for sector, exposure in sector_exposure.items()
                if exposure > self.MAX_SECTOR_EXPOSURE
            }
            
            is_valid = len(violations) == 0
            
            if not is_valid:
                logger.warning(
                    f"Adding {new_ticker} would violate sector limits: {violations}"
                )
            
            return is_valid, sector_exposure
            
        except Exception as e:
            logger.error(f"Error checking sector limits: {e}")
            return True, {}
    
    def validate_new_position(
        self,
        new_ticker: str,
        new_position_value: float,
        existing_positions: List[Dict[str, any]],
        historical_data: Dict[str, pd.DataFrame],
        portfolio_value: float
    ) -> Dict[str, any]:
        """
        Complete validation for adding new position.
        
        Args:
            new_ticker: Ticker to add
            new_position_value: Position value
            existing_positions: Current positions
            historical_data: Historical price data
            portfolio_value: Total portfolio value
            
        Returns:
            Validation results dictionary
        """
        existing_tickers = [p.get('ticker') for p in existing_positions]
        
        # Check correlation
        corr_valid, correlations = self.check_position_correlation(
            new_ticker,
            existing_tickers,
            historical_data
        )
        
        # Check sector limits
        sector_valid, sector_exposure = self.check_sector_limits(
            new_ticker,
            new_position_value,
            existing_positions,
            portfolio_value
        )
        
        # Overall validation
        is_valid = corr_valid and sector_valid
        
        # Build warnings
        warnings = []
        if not corr_valid:
            high_corr = {t: c for t, c in correlations.items() if c >= self.MAX_CORRELATION}
            warnings.append(f"High correlation with: {high_corr}")
        
        if not sector_valid:
            high_sectors = {s: e for s, e in sector_exposure.items() if e > self.MAX_SECTOR_EXPOSURE}
            warnings.append(f"Sector limits exceeded: {high_sectors}")
        
        return {
            'valid': is_valid,
            'correlation_valid': corr_valid,
            'sector_valid': sector_valid,
            'correlations': correlations,
            'sector_exposure': sector_exposure,
            'warnings': warnings,
            'recommendation': (
                'ACCEPT' if is_valid else
                'REDUCE_SIZE' if len(warnings) == 1 else
                'REJECT'
            )
        }
    
    def get_portfolio_diversification_score(
        self,
        positions: List[Dict[str, any]],
        historical_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, any]:
        """
        Calculate portfolio diversification metrics.
        
        Args:
            positions: List of positions
            historical_data: Historical price data
            
        Returns:
            Diversification metrics
        """
        if len(positions) < 2:
            return {'score': 100, 'status': 'well_diversified'}
        
        try:
            # Get returns for all positions
            tickers = [p.get('ticker') for p in positions]
            returns_data = {}
            
            for ticker in tickers:
                if ticker in historical_data:
                    returns_data[ticker] = historical_data[ticker]['Close'].pct_change().iloc[-60:]
            
            if len(returns_data) < 2:
                return {'score': 50, 'status': 'unknown'}
            
            # Calculate average correlation
            corr_matrix = self.calculate_correlation_matrix(returns_data)
            
            # Get upper triangle (exclude diagonal)
            upper_triangle = corr_matrix.where(
                np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
            )
            avg_correlation = upper_triangle.stack().mean()
            
            # Calculate diversification score (0-100)
            # Lower correlation = higher score
            div_score = int((1 - avg_correlation) * 100)
            
            # Classify
            if div_score >= 70:
                status = 'well_diversified'
            elif div_score >= 50:
                status = 'moderately_diversified'
            else:
                status = 'poorly_diversified'
            
            return {
                'score': div_score,
                'avg_correlation': round(avg_correlation, 3),
                'status': status,
                'position_count': len(positions)
            }
            
        except Exception as e:
            logger.error(f"Error calculating diversification: {e}")
            return {'score': 50, 'status': 'unknown'}


# Global instance
portfolio_correlation_manager = PortfolioCorrelationManager()
