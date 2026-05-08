"""Observability service - provider latency/failure telemetry and stale alerts."""
from datetime import datetime, timedelta
from typing import Dict, Any


class ObservabilityService:
    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}

    def record_success(self, provider: str, latency_ms: float):
        m = self.metrics.setdefault(provider, {
            "requests": 0,
            "failures": 0,
            "last_success": None,
            "avg_latency_ms": 0.0
        })
        m["requests"] += 1
        m["last_success"] = datetime.now()
        prev = m["avg_latency_ms"]
        n = m["requests"] - m["failures"]
        m["avg_latency_ms"] = ((prev * max(n - 1, 0)) + latency_ms) / max(n, 1)

    def record_failure(self, provider: str):
        m = self.metrics.setdefault(provider, {
            "requests": 0,
            "failures": 0,
            "last_success": None,
            "avg_latency_ms": 0.0
        })
        m["requests"] += 1
        m["failures"] += 1

    def snapshot(self) -> Dict[str, Any]:
        out = {}
        for provider, m in self.metrics.items():
            req = m.get("requests", 0)
            fail = m.get("failures", 0)
            failure_rate = (fail / req) if req else 0
            out[provider] = {
                "requests": req,
                "failures": fail,
                "failure_rate": round(failure_rate, 4),
                "avg_latency_ms": round(m.get("avg_latency_ms", 0.0), 2),
                "last_success": m.get("last_success"),
            }
        return out

    def stale_alerts(self, stale_after_seconds: int = 180) -> Dict[str, Any]:
        alerts = []
        now = datetime.now()
        for provider, m in self.metrics.items():
            last = m.get("last_success")
            if not last:
                alerts.append({"provider": provider, "severity": "warning", "reason": "no_success_yet"})
                continue
            if now - last > timedelta(seconds=stale_after_seconds):
                alerts.append({
                    "provider": provider,
                    "severity": "high",
                    "reason": "stale_data",
                    "last_success": last
                })
        return {"alerts": alerts, "count": len(alerts)}


observability = ObservabilityService()
