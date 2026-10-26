"""SQLite persistence for history, events, notes and preferences.

SQLite is intended for locally trusted environments; use individual databases or an external
multi-tenant service if isolation across mutually untrusted users is required.
"""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from energychain.memory.base import EnergyMemory, MemoryNote
from energychain.models import EnergyEvent, EnergyReading, Metric, ensure_aware


class SQLiteEnergyMemory(EnergyMemory):
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS readings (
              site TEXT NOT NULL, asset TEXT NOT NULL, metric TEXT NOT NULL,
              value REAL NOT NULL, time TEXT NOT NULL, source TEXT NOT NULL,
              quality TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_readings ON readings(site, asset, metric, time);
            CREATE TABLE IF NOT EXISTS events (
              site TEXT NOT NULL, id TEXT NOT NULL, category TEXT NOT NULL,
              message TEXT NOT NULL, time TEXT NOT NULL, asset TEXT, metadata TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_events ON events(site, time);
            CREATE TABLE IF NOT EXISTS notes (
              site TEXT NOT NULL, category TEXT NOT NULL, text TEXT NOT NULL, time TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_notes ON notes(site);
            CREATE TABLE IF NOT EXISTS preferences (
              site TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
              PRIMARY KEY(site,key));
        """)

    def add_reading(self, site_id: str, reading: EnergyReading) -> None:
        with self._db:
            self._db.execute("INSERT INTO readings VALUES (?,?,?,?,?,?,?,?)", (
                site_id, reading.asset_id, reading.metric.value, reading.value,
                reading.timestamp.isoformat(), reading.source, reading.quality,
                json.dumps(reading.metadata)))

    def history(self, site_id: str, asset_id: str, metric: str, start: datetime,
                end: datetime) -> list[EnergyReading]:
        ensure_aware(start)
        ensure_aware(end)
        # Chronological filtering in Python ensures correct comparison of offset-aware ISO strings.
        records = self._db.execute("SELECT asset,metric,value,time,source,quality,metadata FROM readings WHERE site=? AND asset=? AND metric=?", (site_id, asset_id, Metric(metric).value)).fetchall()
        out = [EnergyReading(a, Metric(m), v, datetime.fromisoformat(t), s, q, json.loads(md))
               for a, m, v, t, s, q, md in records]
        return sorted((r for r in out if start <= r.timestamp <= end), key=lambda r: r.timestamp)

    def add_event(self, event: EnergyEvent) -> None:
        with self._db:
            self._db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)", (
                event.site_id, event.id, event.category, event.message,
                event.timestamp.isoformat(), event.asset_id, json.dumps(event.metadata)))

    def events(self, site_id: str) -> list[EnergyEvent]:
        records = self._db.execute("SELECT id,site,category,message,time,asset,metadata FROM events WHERE site=?", (site_id,)).fetchall()
        return sorted((EnergyEvent(i, s, c, m, datetime.fromisoformat(t), a, json.loads(md))
                       for i, s, c, m, t, a, md in records), key=lambda r: r.timestamp)

    def remember(self, note: MemoryNote) -> None:
        with self._db:
            self._db.execute("INSERT INTO notes VALUES (?,?,?,?)", (note.site_id, note.category, note.text, note.timestamp.isoformat()))

    def recall(self, site_id: str, query: str = "") -> list[MemoryNote]:
        records = self._db.execute("SELECT site,category,text,time FROM notes WHERE site=?", (site_id,)).fetchall()
        return [MemoryNote(s, c, t, datetime.fromisoformat(ts)) for s, c, t, ts in records
                if query.lower() in (t + " " + c).lower()]

    def set_preference(self, site_id: str, key: str, value: Any) -> None:
        if not key:
            raise ValueError("preference key is required")
        with self._db:
            self._db.execute("INSERT INTO preferences VALUES (?,?,?) ON CONFLICT(site,key) DO UPDATE SET value=excluded.value", (site_id, key, json.dumps(value)))

    def preferences(self, site_id: str) -> dict[str, Any]:
        return {k: json.loads(v) for k, v in self._db.execute("SELECT key,value FROM preferences WHERE site=?", (site_id,)).fetchall()}

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "SQLiteEnergyMemory":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
