"""Agent Orchestrator - Manages all agents"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio
import logging

from .market_data_agent import MarketDataAgent
from .technical_agent import TechnicalAnalysisAgent
from .sentiment_agent import SentimentAnalysisAgent
from .news_agent import NewsAnalysisAgent
from .macro_agent import MacroEconomicAgent
from .geopolitical_agent import GeopoliticalRiskAgent
from .whale_agent import WhaleActivityAgent
from .volume_agent import VolumeLiquidityAgent
from .correlation_agent import CorrelationAgent
from .risk_agent import RiskManagementAgent
from .signal_aggregator import SignalAggregatorAgent

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates all AI agents"""
    
    def __init__(self):
        self.agents = {
            "market": MarketDataAgent(),
            "technical": TechnicalAnalysisAgent(),
            "sentiment": SentimentAnalysisAgent(),
            "news": NewsAnalysisAgent(),
            "macro": MacroEconomicAgent(),
            "geopolitical": GeopoliticalRiskAgent(),
            "whale": WhaleActivityAgent(),
            "volume": VolumeLiquidityAgent(),
            "correlation": CorrelationAgent(),
            "risk": RiskManagementAgent(),
            "aggregator": SignalAggregatorAgent()
        }
    
    async def run_all_agents(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run all agents in parallel"""
        tasks = []
        
        for agent_name, agent in self.agents.items():
            if agent_name != "aggregator":
                task = agent.run(context)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        outputs = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Agent error: {result}")
            else:
                outputs.append(result)
        
        return outputs
    
    async def generate_signal(self, symbol: str, asset_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete trading signal"""
        
        # Run all analysis agents
        agent_outputs = await self.run_all_agents(context)
        
        # Run aggregator
        aggregator_context = {
            **context,
            "agent_outputs": agent_outputs
        }
        
        aggregated = await self.agents["aggregator"].run(aggregator_context)
        
        # Get risk data
        risk_output = next((o for o in agent_outputs if o.get("agent_type") == "risk"), {})
        risk_data = risk_output.get("data", {})
        
        # Build final signal
        agg_data = aggregated.get("data", {})
        signal_type = agg_data.get("signal", "hold")
        
        # Map to standard signals
        signal_map = {
            "strong_buy": "strong_buy",
            "buy": "buy",
            "weak_buy": "buy",
            "hold": "hold",
            "weak_sell": "sell",
            "sell": "sell",
            "strong_sell": "strong_sell"
        }
        
        final_signal = signal_map.get(signal_type, "hold")
        confidence = agg_data.get("confidence", 50)
        
        # Calculate entry/stop/take profit
        current_price = context.get("market_data", {}).get("price", 0)
        
        if final_signal in ["buy", "strong_buy"]:
            entry_zone = {
                "min": current_price * 0.98,
                "max": current_price * 1.01
            }
            stop_loss = current_price * 0.95
            take_profit = [current_price * 1.05, current_price * 1.10]
        elif final_signal in ["sell", "strong_sell"]:
            entry_zone = {
                "min": current_price * 0.99,
                "max": current_price * 1.02
            }
            stop_loss = current_price * 1.05
            take_profit = [current_price * 0.95, current_price * 0.90]
        else:
            entry_zone = {"min": current_price * 0.99, "max": current_price * 1.01}
            stop_loss = current_price * 0.97
            take_profit = [current_price * 1.03]
        
        # Build supporting evidence
        evidence = []
        for output in agent_outputs:
            data = output.get("data", {})
            if "signal" in data and data["signal"] not in ["neutral", "normal"]:
                evidence.append(f"{output['agent_name']}: {data['signal']}")
        
        # Build opposing risks
        risks = []
        if risk_data.get("risk_score", 0) > 6:
            risks.append(f"High risk score: {risk_data['risk_score']:.1f}/10")
        
        # Generate thesis
        if final_signal in ["buy", "strong_buy"]:
            thesis = f"Bullish convergence across multiple indicators for {symbol}."
        elif final_signal in ["sell", "strong_sell"]:
            thesis = f"Bearish signals dominant for {symbol}."
        else:
            thesis = f"Mixed signals for {symbol}. Recommend waiting for clearer direction."
        
        return {
            "symbol": symbol,
            "asset_type": asset_type,
            "signal": final_signal,
            "confidence": confidence,
            "risk_score": risk_data.get("risk_score", 5),
            "timeframe": "1d",
            "entry_zone": entry_zone,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "supporting_evidence": evidence[:5],
            "opposing_risks": risks,
            "thesis": thesis,
            "rationale": aggregated.get("analysis", ""),
            "agents_contributed": [o["agent_name"] for o in agent_outputs],
            "agent_outputs": agent_outputs,
            "timestamp": datetime.now(),
            "valid_until": datetime.now() + timedelta(hours=24)
        }
    
    def get_agent_status(self) -> List[Dict[str, Any]]:
        """Get status of all agents"""
        return [agent.get_status() for agent in self.agents.values()]


# Singleton instance
_orchestrator = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
