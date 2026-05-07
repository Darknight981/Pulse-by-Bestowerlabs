"""CoinGecko API Provider - Free crypto data"""
import httpx
import asyncio
import time
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging
from ..core.config import settings
from ..services.observability import observability
from ..services.resilience import retry_async, circuit_breaker

logger = logging.getLogger(__name__)


class CoinGeckoProvider:
    """Free cryptocurrency data from CoinGecko"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Coin ID mapping for common cryptocurrencies
    COIN_IDS = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "BNB": "binancecoin",
        "SOL": "solana",
        "XRP": "ripple",
        "ADA": "cardano",
        "AVAX": "avalanche-2",
        "DOT": "polkadot",
        "MATIC": "matic-network",
        "LINK": "chainlink",
        "UNI": "uniswap",
        "LTC": "litecoin",
        "BCH": "bitcoin-cash",
        "ETC": "ethereum-classic",
        "XLM": "stellar",
        "ALGO": "algorand",
        "VET": "vechain",
        "FIL": "filecoin",
        "TRX": "tron",
        "EOS": "eos",
        "DOGE": "dogecoin",
        "SHIB": "shiba-inu",
        "ATOM": "cosmos",
        "NEAR": "near",
        "APT": "aptos",
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["x-cg-pro-api-key"] = api_key
        self._cache = {}
        self._cache_time = {}
        self._cache_duration = settings.MARKET_DATA_CACHE_SECONDS
        
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
    
    async def _make_request(self, endpoint: str, params: dict = None) -> Optional[Dict]:
        """Make API request with caching and rate limiting"""
        cache_key = self._get_cache_key(endpoint, params or {})
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            if not circuit_breaker.allow("coingecko"):
                logger.warning("CoinGecko circuit open - request blocked")
                return None

            t0 = time.perf_counter()
            async def _request():
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url,
                        params=params or {},
                        headers=self.headers,
                        timeout=30.0
                    )
                    if response.status_code == 429:
                        raise httpx.HTTPStatusError("rate_limited", request=response.request, response=response)
                    response.raise_for_status()
                    return response.json()

            data = await retry_async(_request, retries=2, delay_seconds=0.5)
            self._set_cache(cache_key, data)
            circuit_breaker.mark_success("coingecko")
            observability.record_success("coingecko", (time.perf_counter() - t0) * 1000)
            return data
                
        except Exception as e:
            circuit_breaker.mark_failure("coingecko")
            observability.record_failure("coingecko")
            logger.error(f"CoinGecko API error: {e}")
            return None
    
    async def get_price(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get current prices for symbols"""
        coin_ids = [self.COIN_IDS.get(s.upper(), s.lower()) for s in symbols]
        ids_str = ",".join(coin_ids)
        
        data = await self._make_request(
            "simple/price",
            {
                "ids": ids_str,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
                "include_24hr_high": "true",
                "include_24hr_low": "true"
            }
        )
        
        if not data:
            return {}
            
        # Map back to symbols
        result = {}
        for symbol in symbols:
            coin_id = self.COIN_IDS.get(symbol.upper(), symbol.lower())
            if coin_id in data:
                result[symbol.upper()] = {
                    "price": data[coin_id].get("usd", 0),
                    "change_24h": data[coin_id].get("usd_24h_change", 0),
                    "volume_24h": data[coin_id].get("usd_24h_vol", 0),
                    "market_cap": data[coin_id].get("usd_market_cap", 0),
                    "high_24h": data[coin_id].get("usd_24h_high", 0),
                    "low_24h": data[coin_id].get("usd_24h_low", 0)
                }
        return result
    
    async def get_ohlcv(self, symbol: str, days: int = 30) -> List[Dict]:
        """Get OHLCV data for charting"""
        coin_id = self.COIN_IDS.get(symbol.upper(), symbol.lower())
        
        data = await self._make_request(
            f"coins/{coin_id}/ohlc",
            {
                "vs_currency": "usd",
                "days": str(days)
            }
        )
        
        if not data:
            return []
            
        ohlcv = []
        for candle in data:
            ohlcv.append({
                "timestamp": datetime.fromtimestamp(candle[0] / 1000),
                "open": candle[1],
                "high": candle[2],
                "low": candle[3],
                "close": candle[4]
            })
        return ohlcv
    
    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        """Get comprehensive market data"""
        coin_id = self.COIN_IDS.get(symbol.upper(), symbol.lower())
        
        data = await self._make_request(
            f"coins/{coin_id}",
            {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false"
            }
        )
        
        if not data or "market_data" not in data:
            return None
            
        md = data["market_data"]
        return {
            "name": data.get("name", symbol),
            "symbol": symbol.upper(),
            "price": md.get("current_price", {}).get("usd", 0),
            "change_24h": md.get("price_change_24h", 0),
            "change_percent_24h": md.get("price_change_percentage_24h", 0),
            "volume_24h": md.get("total_volume", {}).get("usd", 0),
            "market_cap": md.get("market_cap", {}).get("usd", 0),
            "high_24h": md.get("high_24h", {}).get("usd", 0),
            "low_24h": md.get("low_24h", {}).get("usd", 0),
            "circulating_supply": md.get("circulating_supply", 0),
            "total_supply": md.get("total_supply", 0),
            "ath": md.get("ath", {}).get("usd", 0),
            "ath_change_percent": md.get("ath_change_percentage", {}).get("usd", 0),
            "last_updated": data.get("last_updated"),
        }
    
    async def get_trending(self) -> List[Dict]:
        """Get trending cryptocurrencies"""
        data = await self._make_request("search/trending", {})
        if not data or "coins" not in data:
            return []
            
        trending = []
        for item in data["coins"]:
            coin = item.get("item", {})
            trending.append({
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", ""),
                "market_cap_rank": coin.get("market_cap_rank", 0),
                "score": coin.get("score", 0)
            })
        return trending
    
    async def get_global_data(self) -> Optional[Dict]:
        """Get global crypto market data"""
        data = await self._make_request("global", {})
        if not data or "data" not in data:
            return None
            
        d = data["data"]
        return {
            "total_market_cap_usd": d.get("total_market_cap", {}).get("usd", 0),
            "total_volume_24h_usd": d.get("total_volume", {}).get("usd", 0),
            "market_cap_change_24h": d.get("market_cap_change_percentage_24h_usd", 0),
            "btc_dominance": d.get("market_cap_percentage", {}).get("btc", 0),
            "eth_dominance": d.get("market_cap_percentage", {}).get("eth", 0),
            "active_cryptocurrencies": d.get("active_cryptocurrencies", 0),
        }


# Singleton instance
_coingecko = None


def get_coingecko() -> CoinGeckoProvider:
    global _coingecko
    if _coingecko is None:
        _coingecko = CoinGeckoProvider()
    return _coingecko
