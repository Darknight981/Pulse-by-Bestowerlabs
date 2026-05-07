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
from ..services.storage import storage
from ..services.observability import observability
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
SESSION_WINDOWS_UTC = {
    "asia": (0, 8),
    "europe": (7, 16),
    "us": (13, 22),
}


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


def _current_market_session() -> str:
    hour = datetime.utcnow().hour
    for name, (start, end) in SESSION_WINDOWS_UTC.items():
        if start <= hour < end:
            return name
    return "off_hours"


def _freshness_score_from_timestamp(ts_value: Any, max_age_seconds: int = 120) -> int:
    """Compute freshness score 0-100 from datetime/iso string."""
    if not ts_value:
        return 0
    try:
        if isinstance(ts_value, datetime):
            ts = ts_value
        else:
            ts = datetime.fromisoformat(str(ts_value).replace("Z", "+00:00")).replace(tzinfo=None)
        age = max((datetime.now() - ts).total_seconds(), 0)
        score = max(0, min(100, int(100 * (1 - (age / max_age_seconds)))))
        return score
    except Exception:
        return 0


def _confidence_from_freshness_and_sources(freshness_score: int, source_count: int, discrepancy_pct: float = 0.0) -> int:
    base = freshness_score
    if source_count >= 2:
        base += 10
    if discrepancy_pct > 0.5:
        base -= 15
    elif discrepancy_pct > 0.25:
        base -= 8
    return max(0, min(100, base))


async def _cross_validate_crypto_price(symbol: str, primary_price: float) -> Dict[str, Any]:
    """Cross-validate crypto price across CoinGecko and Yahoo where available."""
    yahoo = get_yahoo()
    yahoo_symbol = f"{symbol.upper()}-USD"
    yahoo_quote = await yahoo.get_quote(yahoo_symbol, "crypto")
    secondary_price = yahoo_quote.get("price", 0) if yahoo_quote else 0
    if primary_price and secondary_price:
        discrepancy_pct = abs(primary_price - secondary_price) / primary_price
    else:
        discrepancy_pct = 0
    return {
        "secondary_source": "yahoo_finance",
        "secondary_price": secondary_price,
        "discrepancy_pct": discrepancy_pct,
        "discrepancy_flag": discrepancy_pct > 0.02
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
        },
        "telemetry": observability.snapshot(),
        "stale_data_alerts": observability.stale_alerts(180)
    }


@router.post("/system/warm-cache")
async def warm_cache():
    """Warm key caches for dashboard/panel reliability."""
    try:
        cg = get_coingecko()
        yahoo = get_yahoo()
        news_provider = get_news_provider()
        whale = get_whale_monitor()
        await asyncio.gather(
            cg.get_price(["BTC", "ETH", "SOL"]),
            yahoo.get_multiple_quotes(["AAPL", "MSFT", "GOLD", "EURUSD"]),
            news_provider.fetch_all_news(30),
            whale.fetch_whale_transactions("BTC"),
        )
        return {"status": "ok", "warmed": True, "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"Warm cache failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
                fallback = await yahoo.get_quote(f"{symbol}-USD", "crypto")
                if fallback:
                    source = "yahoo_finance_fallback"
                    market_data = {
                        "price": fallback.get("price", 0),
                        "change_24h": fallback.get("change_percent", 0),
                        "volume_24h": fallback.get("volume", 0),
                        "market_cap": fallback.get("market_cap", 0),
                        "high_24h": fallback.get("high", 0),
                        "low_24h": fallback.get("low", 0),
                    }
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

        storage.save_tick(symbol, source, market_data)
        
        return {
            "symbol": symbol,
            "asset_type": asset_type,
            "market_data": {
                "symbol": symbol,
                "asset_type": asset_type,
                **market_data,
                "source": source,
                "source_timestamp": source_timestamp,
                "freshness_score": _freshness_score_from_timestamp(source_timestamp or response_generated_at),
                "confidence_score": _confidence_from_freshness_and_sources(
                    _freshness_score_from_timestamp(source_timestamp or response_generated_at), 1
                ),
                "timestamp": response_generated_at
            },
            "timestamp": response_generated_at
        }
        
    except HTTPException:
        raise
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
        
        storage.save_event("ohlcv_chart", "market_data", {"symbol": symbol, "timeframe": timeframe, "count": len(ohlcv)})

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

        for item in news[:limit]:
            storage.save_news(item.get("source", "rss"), item.get("title", ""), item)
        
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
        for item in news:
            storage.save_news(item.get("source", "rss"), item.get("title", ""), item)

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
        for tx in transactions[:20]:
            storage.save_event("whale_transaction", tx.get("source", "onchain"), tx)
        
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
async def get_signal(
    symbol: str,
    data_quality_mode: str = Query("off", pattern="^(off|warn|strict)$")
):
    """Get AI-generated trading signal.

    data_quality_mode:
    - off: no gating
    - warn: include quality warnings
    - strict: block signal generation when quality is poor
    """
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
        
        market_ts = market_data.get("last_updated") if isinstance(market_data, dict) else None
        latest_news_ts = (news or [{}])[0].get("published_at") if news else None
        quality = {
            "mode": data_quality_mode,
            "has_market_data": bool(market_data),
            "ohlcv_points": len(ohlcv or []),
            "news_items": len(news or []),
            "market_freshness_score": _freshness_score_from_timestamp(market_ts or datetime.now()),
            "news_freshness_score": _freshness_score_from_timestamp(latest_news_ts, max_age_seconds=3600 * 12) if latest_news_ts else 0,
            "warnings": []
        }
        quality["freshness_score"] = int((quality["market_freshness_score"] * 0.7) + (quality["news_freshness_score"] * 0.3))
        if not market_data:
            quality["warnings"].append("market_data_unavailable")
        if len(ohlcv or []) < 20:
            quality["warnings"].append("insufficient_ohlcv_history")
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
        agent_count = len(signal.get("agents_contributed", []))
        quality["agent_count"] = agent_count
        if agent_count < 6:
            quality["warnings"].append("insufficient_agent_coverage")
        if data_quality_mode == "strict" and quality["warnings"]:
            raise HTTPException(status_code=503, detail={"message": "Data quality gate failed", "quality": quality})
        signal["data_quality"] = quality
        storage.save_signal(symbol, signal.get("signal", "hold"), signal.get("confidence", 0), signal)

        return signal
        
    except HTTPException:
        raise
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


@router.get("/agents/calibration")
async def get_signal_calibration():
    """Evaluate realized outcomes from persisted signal history."""
    try:
        orchestrator = get_orchestrator()
        yahoo = get_yahoo()
        watch = ["BTC-USD", "ETH-USD", "AAPL", "MSFT", "GOLD", "EURUSD"]
        latest_prices: Dict[str, float] = {}
        for s in watch:
            q = await yahoo.get_quote(s)
            if q and q.get("price"):
                latest_prices[s.replace("-USD", "")] = float(q["price"])
        calibration = orchestrator.evaluate_realized_outcomes(latest_prices)
        return {
            "calibration": calibration,
            "sample_prices": latest_prices,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error evaluating calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        whale_monitor = get_whale_monitor()
        orchestrator = get_orchestrator()
        
        # Fetch data in parallel
        trending_task = cg.get_trending()
        global_data_task = cg.get_global_data()
        news_task = news_provider.fetch_all_news(30)
        whale_task = whale_monitor.fetch_whale_transactions("BTC")
        
        trending, global_data, news, whale_transactions = await asyncio.gather(
            trending_task, global_data_task, news_task, whale_task
        )
        
        # Get prices for trending
        trending_symbols = [t["symbol"] for t in trending[:5]]
        prices = await cg.get_price(trending_symbols) if trending_symbols else {}
        
        # Build top movers
        top_movers = []
        for sym, data in prices.items():
            source_timestamp = datetime.now()
            freshness_score = _freshness_score_from_timestamp(source_timestamp)
            confidence_score = _confidence_from_freshness_and_sources(freshness_score, 1)
            top_movers.append({
                "symbol": sym,
                "price": data.get("price", 0),
                "change_percent_24h": data.get("change_24h", 0),
                "volume_24h": data.get("volume_24h", 0),
                "source": "coingecko",
                "source_timestamp": source_timestamp,
                "freshness_score": freshness_score,
                "confidence_score": confidence_score
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

        # Enrich news quality metadata
        latest_news = []
        for item in news[:10]:
            freshness = _freshness_score_from_timestamp(item.get("published_at"), max_age_seconds=3600 * 12)
            latest_news.append({
                **item,
                "source": item.get("source", "rss"),
                "freshness_score": freshness,
                "confidence_score": _confidence_from_freshness_and_sources(freshness, 1)
            })

        # Build dashboard macro/geopolitical event sets
        macro_news = _filter_news_by_keywords(news, MACRO_KEYWORDS)[:5]
        geopolitical_news = _filter_news_by_keywords(news, GEOPOLITICAL_KEYWORDS)[:5]
        macro_events = [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "source": item.get("source"),
                "published_at": item.get("published_at"),
                "impact_score": item.get("impact_score", 0),
                "sentiment_label": item.get("sentiment_label", "neutral"),
                "event_type": "macro"
            }
            for item in macro_news
        ]
        macro_events.extend([
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "source": item.get("source"),
                "published_at": item.get("published_at"),
                "impact_score": item.get("impact_score", 0),
                "sentiment_label": item.get("sentiment_label", "neutral"),
                "event_type": "geopolitical"
            }
            for item in geopolitical_news
        ])

        # Build non-empty active signal board for top movers
        active_signals = []
        for mover in top_movers[:3]:
            symbol = mover.get("symbol")
            if not symbol:
                continue
            context = {
                "symbol": symbol,
                "asset_type": "crypto",
                "market_data": mover,
                "ohlcv": [],
                "technicals": {},
                "news": news[:10],
                "whale_data": {"transactions": whale_transactions[:20], "accumulation": {}},
                "macro_events": macro_events[:5],
                "related_prices": {}
            }
            signal = await orchestrator.generate_signal(symbol, "crypto", context)
            signal["source"] = "agent_orchestrator"
            signal["freshness_score"] = _freshness_score_from_timestamp(signal.get("timestamp"))
            signal["confidence_score"] = _confidence_from_freshness_and_sources(
                signal.get("freshness_score", 0), 2 if mover.get("validation", {}).get("secondary_price") else 1
            )
            active_signals.append(signal)

        geo_risk_score = max([e.get("impact_score", 0) for e in geopolitical_news], default=5)
        geo_risk_level = "moderate"
        if geo_risk_score >= 8:
            geo_risk_level = "high"
        elif geo_risk_score >= 6:
            geo_risk_level = "elevated"
        elif geo_risk_score <= 3:
            geo_risk_level = "low"

        # Cross-provider validations for movers
        validated_top_movers = []
        for mover in top_movers[:10]:
            validation = await _cross_validate_crypto_price(mover["symbol"], mover.get("price", 0))
            mover["validation"] = validation
            mover["confidence_score"] = _confidence_from_freshness_and_sources(
                mover.get("freshness_score", 0), 2 if validation.get("secondary_price") else 1, validation.get("discrepancy_pct", 0)
            )
            validated_top_movers.append(mover)

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
            "top_movers": validated_top_movers,
            "trending_assets": [t["symbol"] for t in trending[:10]],
            "latest_news": latest_news,
            "active_signals": active_signals,
            "macro_events": macro_events,
            "whale_activity": [{
                **tx,
                "source": "multi_chain_adapters",
                "freshness_score": _freshness_score_from_timestamp(tx.get("timestamp")),
                "confidence_score": _confidence_from_freshness_and_sources(
                    _freshness_score_from_timestamp(tx.get("timestamp")), 1
                )
            } for tx in whale_transactions[:20]],
            "geopolitical_risk": {
                "overall_risk": geo_risk_score,
                "risk_level": geo_risk_level,
                "active_events": geopolitical_news,
                "affected_regions": [],
                "market_impact": "risk_off" if geo_risk_score >= 6 else "neutral"
            },
            "global_data": global_data,
            "agent_status": {name: "idle" for name in ["market", "technical", "sentiment", "news", "macro", "geopolitical", "whale"]}
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/opportunities")
async def get_opportunity_board(limit: int = 10):
    """Opportunity board derived from mover momentum, confidence and volatility."""
    try:
        dashboard = await get_dashboard_data()
        movers = dashboard.get("top_movers", [])
        signals = {s.get("symbol"): s for s in dashboard.get("active_signals", [])}

        opportunities = []
        for mover in movers[:limit]:
            symbol = mover.get("symbol")
            sig = signals.get(symbol, {})
            confidence = sig.get("confidence", mover.get("confidence_score", 50))
            momentum = abs(mover.get("change_percent_24h", 0))
            score = round((confidence * 0.55) + (min(momentum, 25) * 1.8) + (mover.get("freshness_score", 0) * 0.15), 2)
            opportunities.append({
                "symbol": symbol,
                "signal": sig.get("signal", "hold"),
                "opportunity_score": score,
                "confidence": confidence,
                "price": mover.get("price", 0),
                "change_percent_24h": mover.get("change_percent_24h", 0),
                "risk_score": sig.get("risk_score", 5),
                "source": "opportunity_engine_v1",
                "timestamp": datetime.now()
            })

        opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return {
            "session": _current_market_session(),
            "opportunities": opportunities[:limit],
            "count": min(limit, len(opportunities)),
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error building opportunity board: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/risk/session")
async def get_session_risk_dashboard():
    """Session-based risk dashboard (Asia/Europe/US windows)."""
    try:
        session = _current_market_session()
        macro = await get_global_macro(60)
        geopolitics = await get_global_geopolitics(60)
        dashboard = await get_dashboard_data()

        macro_impact = macro.get("average_impact", 0)
        geo_impact = geopolitics.get("average_impact", 0)
        whale_flow = sum(abs((w.get("netflow_usd", 0) or 0)) for w in dashboard.get("whale_activity", [])[:10])
        normalized_flow = min(10, whale_flow / 50_000_000) if whale_flow else 0
        risk_score = round(min(10, (macro_impact * 0.35) + (geo_impact * 0.45) + (normalized_flow * 0.20)), 2)

        if risk_score >= 8:
            risk_level = "severe"
        elif risk_score >= 6.5:
            risk_level = "high"
        elif risk_score >= 5:
            risk_level = "elevated"
        elif risk_score >= 3:
            risk_level = "moderate"
        else:
            risk_level = "low"

        return {
            "session": session,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "drivers": {
                "macro_average_impact": macro_impact,
                "geopolitical_average_impact": geo_impact,
                "whale_flow_pressure": normalized_flow
            },
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error building session risk dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/regime")
async def get_cross_asset_regime_board():
    """Cross-asset regime board using crypto/equity/commodity/forex momentum proxies."""
    try:
        cg = get_coingecko()
        yahoo = get_yahoo()

        crypto = await cg.get_price(["BTC", "ETH"])
        equities = await yahoo.get_multiple_quotes(["SPY", "QQQ"])
        commodities = await yahoo.get_multiple_quotes(["GOLD", "OIL"])
        forex = await yahoo.get_multiple_quotes(["EURUSD", "USDJPY"])

        def avg_change(payload: Dict[str, Dict], key: str = "change_24h") -> float:
            vals = []
            for item in payload.values():
                vals.append(float(item.get(key, item.get("change_percent", 0)) or 0))
            return round(sum(vals) / len(vals), 3) if vals else 0

        regime = {
            "crypto_momentum": avg_change(crypto, "change_24h"),
            "equity_momentum": avg_change(equities, "change_percent"),
            "commodity_momentum": avg_change(commodities, "change_percent"),
            "forex_momentum": avg_change(forex, "change_percent"),
        }

        risk_on_votes = sum(1 for v in regime.values() if v > 0.25)
        risk_off_votes = sum(1 for v in regime.values() if v < -0.25)
        if risk_on_votes >= 3:
            market_regime = "risk_on"
        elif risk_off_votes >= 3:
            market_regime = "risk_off"
        else:
            market_regime = "mixed"

        return {
            "market_regime": market_regime,
            "signals": regime,
            "risk_on_votes": risk_on_votes,
            "risk_off_votes": risk_off_votes,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error building cross-asset regime board: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/alerts")
async def get_alerts_panel(
    move_threshold_pct: float = 4.0,
    risk_threshold: float = 6.5,
    max_alerts: int = 20
):
    """Alerts panel with threshold rules for movers and risk regime changes."""
    try:
        dashboard = await get_dashboard_data()
        session_risk = await get_session_risk_dashboard()
        regime = await get_cross_asset_regime_board()

        alerts = []
        for mover in dashboard.get("top_movers", []):
            move = abs(mover.get("change_percent_24h", 0))
            if move >= move_threshold_pct:
                alerts.append({
                    "type": "price_move",
                    "severity": "high" if move >= move_threshold_pct * 2 else "medium",
                    "symbol": mover.get("symbol"),
                    "message": f"{mover.get('symbol')} moved {mover.get('change_percent_24h', 0):.2f}% in 24h",
                    "threshold": move_threshold_pct,
                    "observed": move,
                    "timestamp": datetime.now()
                })

        if session_risk.get("risk_score", 0) >= risk_threshold:
            alerts.append({
                "type": "session_risk",
                "severity": "high",
                "symbol": "GLOBAL",
                "message": f"Session risk elevated: {session_risk.get('risk_score')}/10",
                "threshold": risk_threshold,
                "observed": session_risk.get("risk_score", 0),
                "timestamp": datetime.now()
            })

        if regime.get("market_regime") == "risk_off":
            alerts.append({
                "type": "regime_shift",
                "severity": "medium",
                "symbol": "GLOBAL",
                "message": "Cross-asset regime indicates risk-off conditions",
                "threshold": -0.25,
                "observed": regime.get("signals", {}),
                "timestamp": datetime.now()
            })

        alerts.sort(key=lambda a: (a["severity"] == "high", a["timestamp"]), reverse=True)
        return {
            "alerts": alerts[:max_alerts],
            "count": min(len(alerts), max_alerts),
            "rules": {
                "move_threshold_pct": move_threshold_pct,
                "risk_threshold": risk_threshold
            },
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error building alerts panel: {e}")
        raise HTTPException(status_code=500, detail=str(e))
