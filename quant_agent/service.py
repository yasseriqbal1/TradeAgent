"""FastAPI service exposing scanner endpoints."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from datetime import datetime
import sys
from loguru import logger

from .scanner import scanner
from .database import db
from .config import settings, scan_config

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level
)
logger.add(
    "logs/tradeagent_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO"
)

# Initialize FastAPI
app = FastAPI(
    title="TradeAgent API",
    description="Multi-factor stock scanning and analysis API",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "TradeAgent",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "premarket_scan": "/scan/premarket",
            "validation_scan": "/scan/validation",
            "scan_history": "/scan/history"
        }
    }


@app.get("/holdings")
async def get_holdings():
    """
    Get current holdings from config.
    
    Returns the list of tickers currently being tracked (SP100_TICKERS).
    This endpoint allows workflows to dynamically fetch current holdings
    without hardcoding them.
    """
    return {
        "holdings": scan_config.STOCK_UNIVERSE,
        "count": len(scan_config.STOCK_UNIVERSE),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Verifies database connectivity and service status.
    """
    try:
        # Test database connection
        history = db.get_scan_history(limit=1)
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "environment": settings.environment,
            "config": {
                "universe_size": len(scan_config.STOCK_UNIVERSE),
                "top_n": scan_config.TOP_N_SIGNALS,
                "lookback_days": scan_config.LOOKBACK_DAYS
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/scan/premarket")
async def premarket_scan(
    top_n: Optional[int] = Query(
        default=None,
        description="Number of top stocks to return",
        ge=1,
        le=50
    ),
    tickers: Optional[str] = Query(
        default=None,
        description="Comma-separated list of tickers (overrides universe)"
    )
):
    """
    Run pre-market scan (9:00 AM EST).
    
    Scans the configured stock universe using previous day's close data.
    Returns top N stocks by composite score with detailed factor breakdown.
    
    Args:
        top_n: Number of top stocks to return (default: 10)
        tickers: Custom ticker list, comma-separated (optional)
    
    Returns:
        JSON with scan results, signals, and metadata
    """
    try:
        logger.info(f"Pre-market scan requested (top_n={top_n}, custom_tickers={tickers is not None})")
        
        # Parse custom tickers if provided
        ticker_list = None
        if tickers:
            ticker_list = [t.strip().upper() for t in tickers.split(',')]
            logger.info(f"Using custom ticker list: {ticker_list}")
        
        # Run scan
        result = scanner.run_premarket_scan(top_n=top_n, tickers=ticker_list)
        
        if result['status'] == 'failed':
            raise HTTPException(status_code=500, detail=result.get('error', 'Scan failed'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pre-market scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/validation")
async def validation_scan(
    tickers: Optional[str] = Query(
        default=None,
        description="Comma-separated list of tickers to validate (default: latest premarket picks)"
    )
):
    """
    Run validation scan (10:00 AM EST).
    
    Re-scans the top picks from pre-market scan with fresh market data.
    Detects significant changes in scores, prices, or volatility.
    
    Args:
        tickers: Custom ticker list to validate (default: latest premarket picks)
    
    Returns:
        JSON with validation results, changes, and notification flag
    """
    try:
        logger.info("Validation scan requested")
        
        # Parse custom tickers if provided
        ticker_list = None
        if tickers:
            ticker_list = [t.strip().upper() for t in tickers.split(',')]
            logger.info(f"Validating custom ticker list: {ticker_list}")
        
        # Run validation
        result = scanner.run_validation_scan(reference_tickers=ticker_list)
        
        if result['status'] == 'failed':
            raise HTTPException(status_code=500, detail=result.get('error', 'Validation failed'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan/history")
async def scan_history(
    limit: int = Query(
        default=10,
        description="Number of recent scans to return",
        ge=1,
        le=100
    ),
    scan_type: Optional[str] = Query(
        default=None,
        description="Filter by scan type: 'premarket' or 'validation'"
    )
):
    """
    Get scan run history.
    
    Args:
        limit: Number of recent scans to return
        scan_type: Filter by scan type (optional)
    
    Returns:
        List of recent scan runs with metadata
    """
    try:
        history = db.get_scan_history(limit=limit)
        
        # Filter by type if specified
        if scan_type:
            history = [h for h in history if h['scan_type'] == scan_type]
        
        return {
            "count": len(history),
            "scans": history
        }
        
    except Exception as e:
        logger.error(f"History retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/latest")
async def latest_signals(
    scan_type: str = Query(
        default="premarket",
        description="Scan type: 'premarket' or 'validation'"
    )
):
    """
    Get latest signals from most recent scan.
    
    Args:
        scan_type: Type of scan to retrieve signals from
    
    Returns:
        Latest signals from specified scan type
    """
    try:
        signals = db.get_latest_premarket_signals(limit=20)
        
        return {
            "scan_type": scan_type,
            "count": len(signals),
            "signals": signals
        }
        
    except Exception as e:
        logger.error(f"Signals retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config")
async def get_config():
    """Get current scanner configuration."""
    return {
        "universe": {
            "type": "S&P 100",
            "size": len(scan_config.STOCK_UNIVERSE),
            "tickers": scan_config.STOCK_UNIVERSE[:10] + ["..."]
        },
        "parameters": {
            "top_n": scan_config.TOP_N_SIGNALS,
            "lookback_days": scan_config.LOOKBACK_DAYS,
            "min_price": scan_config.MIN_PRICE,
            "min_avg_volume": scan_config.MIN_AVG_VOLUME,
            "max_volatility": scan_config.MAX_VOLATILITY
        },
        "factor_weights": scan_config.FACTOR_WEIGHTS,
        "technical_indicators": {
            "rsi_period": scan_config.RSI_PERIOD,
            "ema_fast": scan_config.EMA_FAST,
            "ema_slow": scan_config.EMA_SLOW,
            "ema_trend": scan_config.EMA_TREND,
            "atr_period": scan_config.ATR_PERIOD
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
