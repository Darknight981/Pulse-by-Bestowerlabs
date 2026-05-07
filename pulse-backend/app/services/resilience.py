"""Resilience utilities: retry and simple circuit breaker."""
from datetime import datetime, timedelta
from typing import Dict
import asyncio


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self.failures: Dict[str, int] = {}
        self.opened_at: Dict[str, datetime] = {}

    def allow(self, key: str) -> bool:
        if key not in self.opened_at:
            return True
        if datetime.now() - self.opened_at[key] > timedelta(seconds=self.reset_timeout_seconds):
            self.failures[key] = 0
            self.opened_at.pop(key, None)
            return True
        return False

    def mark_failure(self, key: str):
        c = self.failures.get(key, 0) + 1
        self.failures[key] = c
        if c >= self.failure_threshold:
            self.opened_at[key] = datetime.now()

    def mark_success(self, key: str):
        self.failures[key] = 0
        self.opened_at.pop(key, None)


async def retry_async(fn, retries: int = 2, delay_seconds: float = 0.4):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(delay_seconds * (attempt + 1))
    raise last_exc


circuit_breaker = CircuitBreaker()
