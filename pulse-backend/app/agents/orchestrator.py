"""Agent Orchestrator - Manages all agents"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio
import logging
import json
import os

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
        self.signal_history_path = os.path.join("data", "signal_history.jsonl")
        self.calibration_path = os.path.join("data", "signal_calibration.json")
    
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
        
        # Build weighted evidence model (hardening v1)
        agg_data = aggregated.get("data", {})
        signal_type = agg_data.get("signal", "hold")
        weighted_evidence = self._build_weighted_evidence(agent_outputs)
        
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
        confidence = int((agg_data.get("confidence", 50) * 0.5) + (weighted_evidence.get("weighted_confidence", 50) * 0.5))
        
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
        
        explainability_trace = {
            "model": "weighted_evidence_v1",
            "weights": weighted_evidence.get("weights", {}),
            "agent_signals": weighted_evidence.get("agent_signals", []),
            "raw_aggregator_signal": signal_type,
            "mapped_final_signal": final_signal,
            "confidence_components": {
                "aggregator_confidence": agg_data.get("confidence", 50),
                "weighted_evidence_confidence": weighted_evidence.get("weighted_confidence", 50),
            }
        }

        final_payload = {
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
            "weighted_evidence": weighted_evidence,
            "explainability_trace": explainability_trace,
            "timestamp": datetime.now(),
            "valid_until": datetime.now() + timedelta(hours=24)
        }
        self._persist_signal(final_payload)
        return final_payload

    def _build_weighted_evidence(self, agent_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        weights = {
            "market_data": 0.15,
            "technical_analysis": 0.2,
            "sentiment_analysis": 0.1,
            "news_analysis": 0.1,
            "macro_economic": 0.1,
            "geopolitical_risk": 0.1,
            "whale_activity": 0.1,
            "volume_liquidity": 0.05,
            "correlation": 0.05,
            "risk_management": 0.05
        }

        score = 0.0
        confidence_acc = 0.0
        total_weight = 0.0
        trace = []
        for output in agent_outputs:
            agent_type = output.get("agent_type", "")
            data = output.get("data", {})
            signal = str(data.get("signal", "neutral")).lower()
            conf = float(output.get("confidence", 50))
            w = weights.get(agent_type, 0.05)
            total_weight += w
            confidence_acc += conf * w

            directional = 0.0
            if "buy" in signal or signal in ["bullish", "accumulation", "positive"]:
                directional = 1.0
            elif "sell" in signal or signal in ["bearish", "distribution", "negative"]:
                directional = -1.0
            score += directional * w
            trace.append({
                "agent_name": output.get("agent_name"),
                "agent_type": agent_type,
                "signal": signal,
                "confidence": conf,
                "weight": w,
                "weighted_contribution": directional * w
            })

        normalized_score = score / total_weight if total_weight else 0
        weighted_confidence = confidence_acc / total_weight if total_weight else 50
        return {
            "score": round(normalized_score, 4),
            "weighted_confidence": round(weighted_confidence, 2),
            "weights": weights,
            "agent_signals": trace
        }

    def _persist_signal(self, signal_payload: Dict[str, Any]) -> None:
        try:
            os.makedirs("data", exist_ok=True)
            serializable = {
                **signal_payload,
                "timestamp": signal_payload.get("timestamp").isoformat() if signal_payload.get("timestamp") else None,
                "valid_until": signal_payload.get("valid_until").isoformat() if signal_payload.get("valid_until") else None
            }
            with open(self.signal_history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(serializable, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist signal history: {e}")

    def evaluate_realized_outcomes(self, latest_prices: Dict[str, float]) -> Dict[str, Any]:
        """Evaluate realized outcomes for persisted signals and return calibration snapshot."""
        if not os.path.exists(self.signal_history_path):
            return {"evaluated": 0, "win_rate": 0, "average_return_pct": 0}

        results = []
        try:
            with open(self.signal_history_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    symbol = row.get("symbol")
                    entry = float(row.get("entry_zone", {}).get("max", 0) or 0)
                    signal = row.get("signal", "hold")
                    current = float(latest_prices.get(symbol, 0) or 0)
                    if not symbol or entry <= 0 or current <= 0:
                        continue
                    ret = (current - entry) / entry
                    if signal in ["sell", "strong_sell"]:
                        ret = -ret
                    if signal == "hold":
                        continue
                    results.append(ret)

            win_rate = (sum(1 for r in results if r > 0) / len(results)) if results else 0
            avg_ret = (sum(results) / len(results)) if results else 0
            snapshot = {
                "evaluated": len(results),
                "win_rate": round(win_rate, 4),
                "average_return_pct": round(avg_ret * 100, 3),
                "timestamp": datetime.now().isoformat()
            }
            with open(self.calibration_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            return snapshot
        except Exception as e:
            logger.error(f"Failed to evaluate realized outcomes: {e}")
            return {"evaluated": 0, "win_rate": 0, "average_return_pct": 0, "error": str(e)}
    
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
