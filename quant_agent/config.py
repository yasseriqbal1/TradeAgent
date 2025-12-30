"""Configuration management for TradeAgent."""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root directory
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
MODELS_DIR = ROOT_DIR / "models"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "tradeagent")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")
    
    # API Keys
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    
    # Email
    email_to: str = os.getenv("EMAIL_TO", "")
    
    # Application
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def database_url(self) -> str:
        """PostgreSQL connection URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


# Stock universe - Simple test tickers (large cap, high liquidity)
SP100_TICKERS = [
    "NVDA", "PLTR", "QBTS", "QUBT", "MU", "RGTI", "SNOW", "IONQ","LAES"
]


class ScanConfig:
    """Scanning configuration."""
    
    # Universe
    STOCK_UNIVERSE: List[str] = SP100_TICKERS
    
    # Scan parameters
    TOP_N_SIGNALS: int = 10
    LOOKBACK_DAYS: int = 30
    
    # Filters
    MIN_PRICE: float = 5.0
    MIN_AVG_VOLUME: int = 500_000
    MAX_VOLATILITY: float = 1.0  # 100% annualized
    
    # Factor weights
    FACTOR_WEIGHTS = {
        "momentum": 0.4,
        "volume": 0.3,
        "volatility": 0.3  # Applied as inverse (lower is better)
    }
    
    # Technical indicator parameters
    RSI_PERIOD: int = 14
    EMA_FAST: int = 9
    EMA_SLOW: int = 21
    EMA_TREND: int = 50
    ATR_PERIOD: int = 14
    VOLATILITY_WINDOW: int = 20
    VOLUME_WINDOW: int = 20
    
    # Return calculation windows
    RETURN_WINDOWS: List[int] = [5, 10, 20]


# Initialize settings
settings = Settings()
scan_config = ScanConfig()
