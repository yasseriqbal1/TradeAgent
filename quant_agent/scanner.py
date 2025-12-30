"""Main scanning logic orchestrating data, factors, and scoring."""

import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .config import scan_config
from .questrade_loader import QuestradeDataLoader  # Use Questrade instead of yfinance
from .factors import factor_calculator
from .scoring import scorer
from .risk_management import risk_manager
from .database import db


class Scanner:
    """Orchestrates the stock scanning process."""
    
    def __init__(self):
        self.universe = scan_config.STOCK_UNIVERSE
        self.data_loader = QuestradeDataLoader()  # Initialize Questrade loader
    
    def run_premarket_scan(self, top_n: int = None, 
                          tickers: List[str] = None) -> Dict[str, Any]:
        """
        Run the pre-market scan (9:00 AM EST).
        
        Uses previous day's close data.
        
        Args:
            top_n: Number of top stocks to return
            tickers: Custom ticker list (default: config universe)
        
        Returns:
            Dictionary with scan results and metadata
        """
        start_time = time.time()
        scan_type = "premarket"
        
        if top_n is None:
            top_n = scan_config.TOP_N_SIGNALS
        
        if tickers is None:
            tickers = self.universe
        
        logger.info(f"Starting {scan_type} scan for {len(tickers)} tickers")
        
        try:
            # Download data
            market_data = self.data_loader.download_universe(
                tickers, 
                period=f"{scan_config.LOOKBACK_DAYS}d",
                use_cache=True
            )
            
            if not market_data:
                raise Exception("No market data available")
            
            logger.info(f"Loaded data for {len(market_data)} tickers")
            
            # Calculate factors for all stocks
            all_factors = []
            for ticker, df in market_data.items():
                factors = factor_calculator.calculate_all_factors(df, ticker)
                
                if factors and factor_calculator.apply_filters(factors):
                    # Get additional info
                    # info = self.data_loader.get_ticker_info(ticker)  # Not available in Questrade
                    # factors.update(info)
                    all_factors.append(factors)
            
            logger.info(f"{len(all_factors)} stocks passed filters")
            
            if not all_factors:
                raise Exception("No stocks passed filters")
            
            # Rank and score
            ranked_factors = scorer.rank_stocks(all_factors)
            top_signals = scorer.select_top_n(ranked_factors, top_n)
            
            # Add risk management to each signal
            for factors in top_signals:
                # Generate complete trade plan with risk metrics
                trade_plan = risk_manager.generate_trade_plan(
                    ticker=factors['ticker'],
                    price=factors['price'],
                    atr=factors.get('atr_14', factors['price'] * 0.02),  # Fallback to 2% of price
                    composite_score=factors['composite_score'],
                    factors=factors,
                    direction='long'
                )
                
                # Add trade plan to factors
                factors['trade_plan'] = trade_plan
            
            # Format signals
            signals = [scorer.format_signal(f, include_detailed=True) for f in top_signals]
            
            # Save to database
            execution_time = time.time() - start_time
            scan_run_id = db.create_scan_run(
                scan_type=scan_type,
                status="success",
                top_n=top_n,
                stocks_scanned=len(market_data),
                execution_time=execution_time
            )
            
            # Save signals and factors
            for i, factors in enumerate(top_signals):
                signal_data = {
                    "ticker": factors['ticker'],
                    "rank": factors['rank'],
                    "composite_score": factors['composite_score'],
                    "price": factors.get('price'),
                    "volume": factors.get('volume'),
                    "market_cap": factors.get('market_cap'),
                    "sector": factors.get('sector'),
                    "selected": True
                }
                
                signal_ids = db.save_signals(scan_run_id, [signal_data])
                
                if signal_ids:
                    db.save_factors(signal_ids[0], factors)
            
            logger.info(f"Scan completed in {execution_time:.2f}s")
            
            return {
                "scan_type": scan_type,
                "timestamp": datetime.now().isoformat(),
                "scan_run_id": scan_run_id,
                "status": "success",
                "execution_time": round(execution_time, 2),
                "stats": {
                    "tickers_requested": len(tickers),
                    "tickers_loaded": len(market_data),
                    "passed_filters": len(all_factors),
                    "top_n": top_n
                },
                "signals": signals
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Scan failed: {e}")
            
            # Log failure to database
            db.create_scan_run(
                scan_type=scan_type,
                status="failed",
                top_n=top_n,
                stocks_scanned=0,
                error_message=str(e),
                execution_time=execution_time
            )
            
            return {
                "scan_type": scan_type,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e),
                "execution_time": round(execution_time, 2)
            }
    
    def run_validation_scan(self, reference_tickers: List[str] = None) -> Dict[str, Any]:
        """
        Run validation scan (10:00 AM EST).
        
        Re-scans the top picks from the pre-market scan with fresh data.
        
        Args:
            reference_tickers: Tickers to validate (default: latest premarket picks)
        
        Returns:
            Dictionary with validation results and changes
        """
        start_time = time.time()
        scan_type = "validation"
        
        logger.info(f"Starting {scan_type} scan")
        
        try:
            # Get reference tickers if not provided
            if reference_tickers is None:
                premarket_signals = db.get_latest_premarket_signals(limit=10)
                if not premarket_signals:
                    raise Exception("No premarket signals found to validate")
                reference_tickers = [s['ticker'] for s in premarket_signals]
            
            logger.info(f"Validating {len(reference_tickers)} tickers from premarket scan")
            
            # Download fresh data (no cache)
            market_data = self.data_loader.download_universe(
                reference_tickers,
                period=f"{scan_config.LOOKBACK_DAYS}d",
                use_cache=False  # Force fresh data
            )
            
            if not market_data:
                raise Exception("No market data available")
            
            # Calculate factors
            all_factors = []
            for ticker, df in market_data.items():
                factors = factor_calculator.calculate_all_factors(df, ticker)
                
                if factors and factor_calculator.apply_filters(factors):
                    # info = self.data_loader.get_ticker_info(ticker)  # Not available in Questrade
                    # factors.update(info)
                    all_factors.append(factors)
            
            logger.info(f"{len(all_factors)} stocks still pass filters")
            
            # Rank and score
            ranked_factors = scorer.rank_stocks(all_factors)
            top_signals = scorer.select_top_n(ranked_factors, len(ranked_factors))
            
            # Add risk management to each signal
            for factors in top_signals:
                # Generate complete trade plan with risk metrics
                trade_plan = risk_manager.generate_trade_plan(
                    ticker=factors['ticker'],
                    price=factors['price'],
                    atr=factors.get('atr_14', factors['price'] * 0.02),
                    composite_score=factors['composite_score'],
                    factors=factors,
                    direction='long'
                )
                
                # Add trade plan to factors
                factors['trade_plan'] = trade_plan
            
            # Format signals
            signals = [scorer.format_signal(f, include_detailed=True) for f in top_signals]
            
            # Compare with premarket
            premarket_signals = db.get_latest_premarket_signals(limit=10)
            changes = scorer.compare_signals(premarket_signals, signals)
            
            # Save to database
            execution_time = time.time() - start_time
            scan_run_id = db.create_scan_run(
                scan_type=scan_type,
                status="success",
                top_n=len(signals),
                stocks_scanned=len(market_data),
                execution_time=execution_time
            )
            
            # Save signals and factors
            for factors in top_signals:
                signal_data = {
                    "ticker": factors['ticker'],
                    "rank": factors['rank'],
                    "composite_score": factors['composite_score'],
                    "price": factors.get('price'),
                    "volume": factors.get('volume'),
                    "market_cap": factors.get('market_cap'),
                    "sector": factors.get('sector'),
                    "selected": True
                }
                
                signal_ids = db.save_signals(scan_run_id, [signal_data])
                
                if signal_ids:
                    db.save_factors(signal_ids[0], factors)
            
            logger.info(f"Validation scan completed in {execution_time:.2f}s")
            
            # Determine if changes warrant notification
            has_significant_changes = (
                len(changes['dropped']) > 0 or
                len(changes['added']) > 0 or
                len(changes['price_moves']) > 2
            )
            
            return {
                "scan_type": scan_type,
                "timestamp": datetime.now().isoformat(),
                "scan_run_id": scan_run_id,
                "status": "success",
                "execution_time": round(execution_time, 2),
                "stats": {
                    "tickers_validated": len(reference_tickers),
                    "tickers_loaded": len(market_data),
                    "still_passing": len(all_factors)
                },
                "signals": signals,
                "changes": changes,
                "notify": has_significant_changes
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Validation scan failed: {e}")
            
            db.create_scan_run(
                scan_type=scan_type,
                status="failed",
                top_n=0,
                stocks_scanned=0,
                error_message=str(e),
                execution_time=execution_time
            )
            
            return {
                "scan_type": scan_type,
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e),
                "execution_time": round(execution_time, 2)
            }


# Global scanner instance
scanner = Scanner()
