"""Yahoo Finance Provider - Free stock and commodity data"""
import httpx
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)


class YahooFinanceProvider:
    """Free stock and commodity data from Yahoo Finance"""
    
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
    
    # Symbol mappings
    SYMBOL_MAP = {
        # UK Stocks (LSE)
        "SHEL": "SHEL.L",
        "AZN": "AZN.L",
        "ULVR": "ULVR.L",
        "HSBA": "HSBA.L",
        "BP": "BP.L",
        "RIO": "RIO.L",
        "GSK": "GSK.L",
        "BARC": "BARC.L",
        "LLOY": "LLOY.L",
        "VOD": "VOD.L",
        "BT-A": "BT-A.L",
        "TSCO": "TSCO.L",
        "BA": "BA.L",
        "RR": "RR.L",
        "JD": "JD.L",
        "III": "III.L",
        "CRH": "CRH.L",
        "REL": "REL.L",
        "CPG": "CPG.L",
        # Commodities
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "OIL": "CL=F",
        "BRENT": "BZ=F",
        "NATGAS": "NG=F",
        "COPPER": "HG=F",
        "WHEAT": "ZW=F",
        "CORN": "ZC=F",
        # Forex
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "JPY=X",
        "USDCHF": "CHF=X",
        "AUDUSD": "AUDUSD=X",
        "USDCAD": "CAD=X",
        "NZDUSD": "NZDUSD=X",
    }
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self._cache = {}
        self._cache_time = {}
        self._cache_duration = settings.MARKET_DATA_CACHE_SECONDS
        
    def _get_yahoo_symbol(self, symbol: str, asset_type: str = None) -> str:
        """Convert symbol to Yahoo Finance format"""
        upper_sym = symbol.upper()
        if upper_sym in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[upper_sym]
        return upper_sym
    
    def _get_cache_key(self, endpoint: str, params: dict) -> str:
        return f"{endpoint}:{hash(str(sorted(params.items())))}"
    
    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._cache:
            if datetime.now() - self._cache_time[key] < timedelta(seconds=self._cache_duration):
                return self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: Any):
        self._cache[key] = data
        self._cache_time[key] = datetime.now()
    
    async def _make_request(self, url: str, params: dict = None) -> Optional[Dict]:
        """Make API request"""
        cache_key = self._get_cache_key(url, params or {})
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url, 
                    params=params or {}, 
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                self._set_cache(cache_key, data)
                return data
                
        except Exception as e:
            logger.error(f"Yahoo Finance API error: {e}")
            return None
    
    async def get_quote(self, symbol: str, asset_type: str = None) -> Optional[Dict]:
        """Get stock/commodity quote"""
        yahoo_sym = self._get_yahoo_symbol(symbol, asset_type)
        
        data = await self._make_request(
            f"{self.QUOTE_URL}/{yahoo_sym}",
            {"symbols": yahoo_sym}
        )
        
        if not data or "quoteResponse" not in data:
            return None
            
        quotes = data["quoteResponse"].get("result", [])
        if not quotes:
            return None
            
        q = quotes[0]
        return {
            "symbol": symbol.upper(),
            "name": q.get("longName", q.get("shortName", symbol)),
            "price": q.get("regularMarketPrice", 0),
            "change": q.get("regularMarketChange", 0),
            "change_percent": q.get("regularMarketChangePercent", 0),
            "volume": q.get("regularMarketVolume", 0),
            "market_cap": q.get("marketCap", 0),
            "high": q.get("regularMarketDayHigh", 0),
            "low": q.get("regularMarketDayLow", 0),
            "open": q.get("regularMarketOpen", 0),
            "previous_close": q.get("regularMarketPreviousClose", 0),
            "fifty_two_week_high": q.get("fiftyTwoWeekHigh", 0),
            "fifty_two_week_low": q.get("fiftyTwoWeekLow", 0),
            "pe_ratio": q.get("trailingPE", 0),
            "dividend_yield": q.get("dividendYield", 0),
            "market_time": q.get("regularMarketTime"),
            "market_state": q.get("marketState", "UNKNOWN"),
            "exchange_timezone": q.get("exchangeTimezoneShortName", "UTC"),
        }
    
    async def get_ohlcv(self, symbol: str, interval: str = "1d", range_period: str = "1mo") -> List[Dict]:
        """Get OHLCV data"""
        yahoo_sym = self._get_yahoo_symbol(symbol)
        
        data = await self._make_request(
            f"{self.BASE_URL}/{yahoo_sym}",
            {
                "interval": interval,
                "range": range_period,
                "includeAdjustedClose": "true",
                "includePrePost": "true"
            }
        )
        
        if not data or "chart" not in data:
            return []
            
        chart = data["chart"]
        if "result" not in chart or not chart["result"]:
            return []
            
        result = chart["result"][0]
        timestamps = result.get("timestamp", [])
        ohlc = result.get("indicators", {}).get("quote", [{}])[0]
        
        ohlcv = []
        for i, ts in enumerate(timestamps):
            if all(k in ohlc and ohlc[k] and len(ohlc[k]) > i for k in ["open", "high", "low", "close", "volume"]):
                ohlcv.append({
                    "timestamp": datetime.fromtimestamp(ts),
                    "open": ohlc["open"][i],
                    "high": ohlc["high"][i],
                    "low": ohlc["low"][i],
                    "close": ohlc["close"][i],
                    "volume": ohlc["volume"][i]
                })
        return ohlcv
    
    async def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get quotes for multiple symbols"""
        results = {}
        for symbol in symbols:
            quote = await self.get_quote(symbol)
            if quote:
                results[symbol.upper()] = quote
        return results


# Singleton instance
_yahoo = None


def get_yahoo() -> YahooFinanceProvider:
    global _yahoo
    if _yahoo is None:
        _yahoo = YahooFinanceProvider()
    return _yahoo
