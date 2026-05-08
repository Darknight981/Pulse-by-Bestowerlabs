"""Durable storage service for ticks/news/events/signals via SQLite."""
import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List


class StorageService:
    def __init__(self, db_path: str = "data/pulse_data.db"):
        os.makedirs("data", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS ticks(ts TEXT, symbol TEXT, source TEXT, payload TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS news(ts TEXT, source TEXT, title TEXT, payload TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS events(ts TEXT, event_type TEXT, source TEXT, payload TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS signals(ts TEXT, symbol TEXT, signal TEXT, confidence REAL, payload TEXT)")
            conn.commit()

    def save_tick(self, symbol: str, source: str, payload: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO ticks(ts, symbol, source, payload) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), symbol, source, json.dumps(payload, default=str)),
            )
            conn.commit()

    def save_news(self, source: str, title: str, payload: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO news(ts, source, title, payload) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), source, title, json.dumps(payload, default=str)),
            )
            conn.commit()

    def save_event(self, event_type: str, source: str, payload: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events(ts, event_type, source, payload) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), event_type, source, json.dumps(payload, default=str)),
            )
            conn.commit()

    def save_signal(self, symbol: str, signal: str, confidence: float, payload: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO signals(ts, symbol, signal, confidence, payload) VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), symbol, signal, float(confidence), json.dumps(payload, default=str)),
            )
            conn.commit()


storage = StorageService()
