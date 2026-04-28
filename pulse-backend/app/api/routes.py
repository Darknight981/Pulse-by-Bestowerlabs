"""API Routes - All endpoints"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import logging
from statistics import mean

from ..providers.coingecko import get_coingecko
from ..providers.yahoo import get_yahoo
from ..providers.news import get_news_provider
from ..providers.whale import get_whale_monitor
from ..services.technical_analysis import ta_service
from ..agents.orchestrator import get_orchestrator
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

MACRO_KEYWORDS = [
    "federal reserve", "fed", "fomc", "interest rate", "inflation", "cpi", "ppi",
    "gdp", "unemployment", "central bank", "ecb", "boe", "bank of england", "monetary policy"
]

GEOPOLITICAL_KEYWORDS = [
    "war", "conflict", "sanction", "tariff", "election", "oil supply", "opec",
    "geopolitical", "regulation", "policy", "tension", "military"
]


def _filter_news_by_keywords(news_items: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    filtered = []
    for item in news_items:
        haystack = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        if any(keyword in haystack for keyword in keywords):
            filtered.append(item)
    return filtered


def _build_news_intelligence(news_items: List[Dict[str, Any]], category: str) -> Dict[str, Any]:
    if not news_items:
        return {
            "category": category,
            "count": 0,
            "average_sentiment": 0,
            "average_impact": 0,
            "highest_impact": None,
            "risk_mode": "neutral",
            "events": []
        }

    avg_sentiment = mean([n.get("sentiment_score", 0) for n in news_items])
    avg_impact = mean([n.get("impact_score", 0) for n in news_items])
    highest_impact = max(news_items, key=lambda n: n.get("impact_score", 0))

    if avg_sentiment < -0.15:
        risk_mode = "risk_off"
    elif avg_sentiment > 0.15:
        risk_mode = "risk_on"
    else:
        risk_mode = "neutral"

    return {
        "category": category,
        "count": len(news_items),
        "average_sentiment": round(avg_sentiment, 3),
        "average_impact": round(avg_impact, 3),
        "highest_impact": highest_impact,
        "risk_mode": risk_mode,
        "events": news_items[:25],
    }


# Health check
@router.get("/system/health")
async def health_check():
    """System health status"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(),
        "services": {
            "api": {"status": "up"},
            "data_providers": {"status": "up"},
            "agents": {"status": "up"}
        }
    }


# Asset search
@router.get("/assets/search")
async def search_assets(
    query: str = Query(..., min_length=1),
    asset_type: Optional[str] = None
):
    """Search for assets"""
    results = []
    
    # Search crypto
    if not asset_type or asset_type == "crypto":
        crypto_symbols = [s for s in settings.SUPPORTED_CRYPTO if query.upper() in s]
        for sym in crypto_symbols[:5]:
            results.append({
                "symbol": sym,
                "name": sym,
                "asset_type": "crypto",
                "exchange": "Multiple"
            })
    
    # Search stocks
    if not asset_type or asset_type in ["us_stock", "uk_stock"]:
        us_stocks = [s for s in settings.SUPPORTED_US_STOCKS if query.upper() in s]
        for sym in us_stocks[:5]:
            results.append({
                "symbol": sym,
                "name": sym,
                "asset_type": "us_stock",
                "exchange": "NYSE/NASDAQ"
            })
        
        uk_stocks = [s for s in settings.SUPPORTED_UK_STOCKS if query.upper() in s]
        for sym in uk_stocks[:5]:
            results.append({
                "symbol": sym,
                "name": sym,
                "asset_type": "uk_stock",
                "exchange": "LSE"
            })
    
    # Search commodities
    if not asset_type or asset_type == "commodity":
        commodities = [s for s in settings.SUPPORTED_COMMODITIES if query.upper() in s]
        for sym in commodities[:5]:
            results.append({
                "symbol": sym,
                "name": sym,
                "asset_type": "commodity",
                "exchange": "CME/COMEX"
            })

    # Search forex
    if not asset_type or asset_type == "forex":
        forex_pairs = [s for s in settings.SUPPORTED_FOREX if query.upper() in s]
        for sym in forex_pairs[:5]:
            results.append({
                "symbol": sym,
                "name": sym,
                "asset_type": "forex",
                "exchange": "FX Spot"
            })
    
    return {"results": results[:10]}


# Asset overview
@router.get("/assets/{symbol}/overview")
async def get_asset_overview(symbol: str):
    """Get complete asset overview"""
    symbol = symbol.upper()
    
    # Determine asset type
    if symbol in settings.SUPPORTED_CRYPTO:
        asset_type = "crypto"
    elif symbol in settings.SUPPORTED_US_STOCKS:
        asset_type = "us_stock"
    elif symbol in settings.SUPPORTED_UK_STOCKS:
        asset_type = "uk_stock"
    elif symbol in settings.SUPPORTED_COMMODITIES:
        asset_type = "commodity"
    elif symbol in settings.SUPPORTED_FOREX:
        asset_type = "forex"
    else:
        asset_type = "crypto"  # Default to crypto
    
    try:
        response_generated_at = datetime.now()
        source = "unknown"
        source_timestamp = None

        # Fetch market data
        if asset_type == "crypto":
            cg = get_coingecko()
            market_data = await cg.get_market_data(symbol)
            if market_data:
                source = "coingecko"
                market_data["change_24h"] = market_data.get("change_percent_24h", 0)
                market_data["volume_24h"] = market_data.get("volume_24h", 0)
                market_data["high_24h"] = market_data.get("high_24h", 0)
                market_data["low_24h"] = market_data.get("low_24h", 0)
                source_timestamp = market_data.get("last_updated")
        else:
            yahoo = get_yahoo()
            quote = await yahoo.get_quote(symbol, asset_type)
            if quote:
                source = "yahoo_finance"
                quote_market_time = quote.get("market_time")
                if quote_market_time:
                    source_timestamp = datetime.fromtimestamp(quote_market_time).isoformat()
                market_data = {
                    "price": quote.get("price", 0),
                    "change_24h": quote.get("change_percent", 0),
                    "volume_24h": quote.get("volume", 0),
                    "market_cap": quote.get("market_cap", 0),
                    "high_24h": quote.get("high", 0),
                    "low_24h": quote.get("low", 0),
                    "market_state": quote.get("market_state"),
                    "exchange_timezone": quote.get("exchange_timezone")
                }
            else:
                market_data = {}
        
        if not market_data:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        
        return {
            "symbol": symbol,
            "asset_type": asset_type,
            "market_data": {
                "symbol": symbol,
                "asset_type": asset_type,
                **market_data,
                "source": source,
                "source_timestamp": source_timestamp,
                "timestamp": response_generated_at
            },
            "timestamp": response_generated_at
        }
        
    except Exception as e:
        logger.error(f"Error fetching overview for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Chart data
@router.get("/assets/{symbol}/chart")
async def get_chart_data(
    symbol: str,
    timeframe: str = "1d",
    days: int = 30
):
    """Get OHLCV chart data"""
    symbol = symbol.upper()
    
    try:
        # Determine asset type
        if symbol in settings.SUPPORTED_CRYPTO:
            cg = get_coingecko()
            ohlcv = await cg.get_ohlcv(symbol, days)
        else:
            yahoo = get_yahoo()
            timeframe_to_interval = {
                "1h": "5m",
                "1d": "1h",
                "1w": "1d"
            }
            interval = timeframe_to_interval.get(timeframe, "1h" if days <= 7 else "1d")
            range_period = f"{days}d" if days <= 60 else "1y"
            ohlcv = await yahoo.get_ohlcv(symbol, interval, range_period)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data": ohlcv
        }
        
    except Exception as e:
        logger.error(f"Error fetching chart for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Technical analysis
@router.get("/assets/{symbol}/technicals")
async def get_technicals(symbol: str, timeframe: str = "1d"):
    """Get technical analysis"""
    symbol = symbol.upper()
    
    try:
        # Get chart data
        if symbol in settings.SUPPORTED_CRYPTO:
            cg = get_coingecko()
            ohlcv = await cg.get_ohlcv(symbol, 50)
        else:
            yahoo = get_yahoo()
            ohlcv = await yahoo.get_ohlcv(symbol, "1d", "2mo")
        
        if not ohlcv or len(ohlcv) < 20:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "indicators": {},
                "signals": [],
                "trend": "unknown"
            }
        
        closes = [c["close"] for c in ohlcv]
        highs = [c["high"] for c in ohlcv]
        lows = [c["low"] for c in ohlcv]
        
        # Calculate indicators
        rsi = ta_service.calculate_rsi(closes)
        macd = ta_service.calculate_macd(closes)
        bb = ta_service.calculate_bollinger_bands(closes)
        trend = ta_service.analyze_trend(closes)
        support, resistance = ta_service.find_support_resistance(closes)
        signals = ta_service.generate_signals(ohlcv)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": {
                "rsi": rsi[-1] if rsi else 50,
                "macd": macd["macd"][-1] if macd["macd"] else 0,
                "macd_signal": macd["signal"][-1] if macd["signal"] else 0,
                "bb_upper": bb["upper"][-1] if bb["upper"] else closes[-1],
                "bb_middle": bb["middle"][-1] if bb["middle"] else closes[-1],
                "bb_lower": bb["lower"][-1] if bb["lower"] else closes[-1],
                "sma_20": sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1],
                "sma_50": sum(closes[-50:]) / 50 if len(closes) >= 50 else closes[-1]
            },
            "signals": signals.get("signals", []),
            "trend": trend,
            "support_levels": support,
            "resistance_levels": resistance,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error fetching technicals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# News
@router.get("/assets/{symbol}/news")
async def get_asset_news(symbol: str, limit: int = 20):
    """Get news for asset"""
    symbol = symbol.upper()
    
    try:
        news_provider = get_news_provider()
        news = await news_provider.get_news_for_asset(symbol, "crypto")
        
        return {
            "symbol": symbol,
            "news": news[:limit],
            "count": len(news[:limit])
        }
        
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Global news
@router.get("/global/news")
async def get_global_news(limit: int = 50):
    """Get global financial news"""
    try:
        news_provider = get_news_provider()
        news = await news_provider.fetch_all_news(limit)
        
        return {
            "news": news,
            "count": len(news),
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error fetching global news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Global macro intelligence
@router.get("/global/macro")
async def get_global_macro(limit: int = 100):
    """Get macroeconomic intelligence from live news stream"""
    try:
        news_provider = get_news_provider()
        news = await news_provider.fetch_all_news(limit)
        macro_news = _filter_news_by_keywords(news, MACRO_KEYWORDS)
        intelligence = _build_news_intelligence(macro_news, "macro")

        return {
            "timestamp": datetime.now(),
            **intelligence
        }
    except Exception as e:
        logger.error(f"Error fetching macro intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Global geopolitical intelligence
@router.get("/global/geopolitics")
async def get_global_geopolitics(limit: int = 100):
    """Get geopolitical intelligence from live news stream"""
    try:
        news_provider = get_news_provider()
        news = await news_provider.fetch_all_news(limit)
        geopolitical_news = _filter_news_by_keywords(news, GEOPOLITICAL_KEYWORDS)
        intelligence = _build_news_intelligence(geopolitical_news, "geopolitical")

        return {
            "timestamp": datetime.now(),
            **intelligence
        }
    except Exception as e:
        logger.error(f"Error fetching geopolitical intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Whale data
@router.get("/assets/{symbol}/flow")
async def get_flow_data(symbol: str):
    """Get whale/exchange flow data"""
    symbol = symbol.upper()
    
    try:
        whale_monitor = get_whale_monitor()
        
        transactions = await whale_monitor.fetch_whale_transactions(symbol)
        flows = await whale_monitor.get_exchange_flows(symbol)
        accumulation = await whale_monitor.get_accumulation_trend(symbol)
        
        return {
            "symbol": symbol,
            "transactions": transactions,
            "exchange_flows": flows,
            "accumulation_trend": accumulation,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Error fetching flow data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Signal generation
@router.get("/assets/{symbol}/signal")
async def get_signal(symbol: str):
    """Get AI-generated trading signal"""
    symbol = symbol.upper()
    
    try:
        # Determine asset type
        if symbol in settings.SUPPORTED_CRYPTO:
            asset_type = "crypto"
        elif symbol in settings.SUPPORTED_US_STOCKS:
            asset_type = "us_stock"
        elif symbol in settings.SUPPORTED_UK_STOCKS:
            asset_type = "uk_stock"
        elif symbol in settings.SUPPORTED_COMMODITIES:
            asset_type = "commodity"
        elif symbol in settings.SUPPORTED_FOREX:
            asset_type = "forex"
        else:
            asset_type = "crypto"
        
        # Gather all data
        cg = get_coingecko()
        yahoo = get_yahoo()
        news_provider = get_news_provider()
        whale_monitor = get_whale_monitor()
        
        # Fetch data in parallel
        if asset_type == "crypto":
            market_data_task = cg.get_market_data(symbol)
            ohlcv_task = cg.get_ohlcv(symbol, 50)
        else:
            market_data_task = yahoo.get_quote(symbol, asset_type)
            ohlcv_task = yahoo.get_ohlcv(symbol, "1d", "2mo")
        
        news_task = news_provider.get_news_for_asset(symbol, asset_type)
        whale_task = whale_monitor.get_accumulation_trend(symbol)
        
        market_data, ohlcv, news, whale_data = await asyncio.gather(
            market_data_task, ohlcv_task, news_task, whale_task
        )
        
        # Format market data
        if asset_type != "crypto" and market_data:
            market_data = {
                "price": market_data.get("price", 0),
                "change_percent_24h": market_data.get("change_percent", 0),
                "volume_24h": market_data.get("volume", 0),
                "market_cap": market_data.get("market_cap", 0),
                "high_24h": market_data.get("high", 0),
                "low_24h": market_data.get("low", 0)
            }
        
        # Calculate technicals
        technicals = {}
        if ohlcv and len(ohlcv) >= 20:
            closes = [c["close"] for c in ohlcv]
            technicals = {
                "rsi": ta_service.calculate_rsi(closes)[-1],
                "trend": ta_service.analyze_trend(closes),
                "signals": ta_service.generate_signals(ohlcv).get("signals", [])
            }
        
        # Build context
        context = {
            "symbol": symbol,
            "asset_type": asset_type,
            "market_data": market_data or {},
            "ohlcv": ohlcv or [],
            "technicals": technicals,
            "news": news or [],
            "whale_data": {
                "transactions": [],
                "accumulation": whale_data
            },
            "macro_events": [],
            "related_prices": {}
        }
        
        # Run agent orchestration
        orchestrator = get_orchestrator()
        signal = await orchestrator.generate_signal(symbol, asset_type, context)
        
        return signal
        
    except Exception as e:
        logger.error(f"Error generating signal for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agents status
@router.get("/agents")
async def get_agents_status():
    """Get all agent statuses"""
    orchestrator = get_orchestrator()
    return {
        "agents": orchestrator.get_agent_status(),
        "timestamp": datetime.now()
    }


# Run specific agent
@router.post("/agents/{agent_name}/run")
async def run_agent(agent_name: str, context: Dict[str, Any]):
    """Run a specific agent"""
    orchestrator = get_orchestrator()
    
    agent = orchestrator.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    result = await agent.run(context)
    return result


@router.get("/agents/{agent_name}/status")
async def get_agent_status(agent_name: str):
    """Get status for a specific agent"""
    orchestrator = get_orchestrator()
    agent = orchestrator.agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    return {
        "agent": agent_name,
        "status": agent.get_status(),
        "timestamp": datetime.now()
    }


# Dashboard data
@router.get("/dashboard")
async def get_dashboard_data():
    """Get complete dashboard data"""
    try:
        cg = get_coingecko()
        news_provider = get_news_provider()
        
        # Fetch data in parallel
        trending_task = cg.get_trending()
        global_data_task = cg.get_global_data()
        news_task = news_provider.fetch_all_news(20)
        
        trending, global_data, news = await asyncio.gather(
            trending_task, global_data_task, news_task
        )
        
        # Get prices for trending
        trending_symbols = [t["symbol"] for t in trending[:5]]
        prices = await cg.get_price(trending_symbols) if trending_symbols else {}
        
        # Build top movers
        top_movers = []
        for sym, data in prices.items():
            top_movers.append({
                "symbol": sym,
                "price": data.get("price", 0),
                "change_percent_24h": data.get("change_24h", 0),
                "volume_24h": data.get("volume_24h", 0)
            })
        
        # Sort by change
        top_movers.sort(key=lambda x: abs(x["change_percent_24h"]), reverse=True)
        
        market_cap_change = (global_data or {}).get("market_cap_change_24h", 0)
        fear_greed_index = max(0, min(100, int(50 + market_cap_change * 4)))
        if fear_greed_index >= 75:
            sentiment_label = "extreme_greed"
        elif fear_greed_index >= 60:
            sentiment_label = "greed"
        elif fear_greed_index <= 25:
            sentiment_label = "extreme_fear"
        elif fear_greed_index <= 40:
            sentiment_label = "fear"
        else:
            sentiment_label = "neutral"

        return {
            "timestamp": datetime.now(),
            "market_sentiment": {
                "overall_score": fear_greed_index,
                "label": sentiment_label,
                "fear_greed_index": fear_greed_index,
                "crypto_score": fear_greed_index,
                "equities_score": 50,
                "commodities_score": 50
            },
            "top_movers": top_movers[:10],
            "trending_assets": [t["symbol"] for t in trending[:10]],
            "latest_news": news[:10],
            "active_signals": [],
            "macro_events": [],
            "whale_activity": [],
            "geopolitical_risk": {
                "overall_risk": 5,
                "risk_level": "moderate",
                "active_events": [],
                "affected_regions": [],
                "market_impact": "neutral"
            },
            "global_data": global_data,
            "agent_status": {name: "idle" for name in ["market", "technical", "sentiment", "news", "macro", "geopolitical", "whale"]}
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
