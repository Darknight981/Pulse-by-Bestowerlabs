"""PULSE Configuration - Environment variables and settings"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings"""
    # App
    APP_NAME: str = "PULSE by Bestower Labs"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Security
    SECRET_KEY: str = "pulse-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/pulse.db"
    
    # Redis (for caching)
    REDIS_URL: Optional[str] = None
    
    # API Keys (free tiers)
    COINGECKO_API_KEY: Optional[str] = None
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    NEWS_API_KEY: Optional[str] = None
    FINANCIAL_MODELING_PREP_API_KEY: Optional[str] = None
    ETHERSCAN_API_KEY: Optional[str] = None
    BLOCKCHAIR_API_KEY: Optional[str] = None
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Data refresh intervals (seconds)
    PRICE_REFRESH_INTERVAL: int = 1
    NEWS_REFRESH_INTERVAL: int = 300
    SIGNAL_REFRESH_INTERVAL: int = 60
    MARKET_DATA_CACHE_SECONDS: int = 1
    
    # Asset coverage
    SUPPORTED_CRYPTO: List[str] = [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOT", "MATIC", "LINK",
        "UNI", "LTC", "BCH", "ETC", "XLM", "ALGO", "VET", "FIL", "TRX", "EOS"
    ]
    
    SUPPORTED_US_STOCKS: List[str] = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX", "AMD", "INTC",
        "IBM", "ORCL", "CSCO", "ADBE", "CRM", "PYPL", "UBER", "LYFT", "ZM", "SHOP"
    ]
    
    SUPPORTED_UK_STOCKS: List[str] = [
        "SHEL", "AZN", "ULVR", "HSBA", "BP", "RIO", "GSK", "BARC", "LLOY", "VOD",
        "BT-A", "TSCO", "BA", "RR", "JD", "III", "CRH", "REL", "CPG", "SMUR"
    ]
    
    SUPPORTED_COMMODITIES: List[str] = [
        "GOLD", "SILVER", "OIL", "BRENT", "NATGAS", "COPPER", "WHEAT", "CORN"
    ]
    
    SUPPORTED_FOREX: List[str] = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"
    ]
    
    # News sources
    NEWS_SOURCES: List[str] = [
        "reuters", "bloomberg", "coindesk", "cointelegraph", "cryptonews",
        "financial-times", "wsj", "cnbc", "marketwatch"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
