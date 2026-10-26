"""Isolated, bounded, in-process memory for prototypes and tests."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from typing import Any
from energychain.models import EnergyEvent, EnergyReading, Metric, ensure_aware
from energychain.memory.base import EnergyMemory, MemoryNote


class InMemoryEnergyMemory(EnergyMemory):
    def __init__(self, *, max_records_per_site: int = 10_000) -> None:
        if max_records_per_site < 1:
            raise ValueError("max_records_per_site must be positive")
        self.max_records = max_records_per_site
        self._readings: dict[str, list[EnergyReading]] = defaultdict(list)
        self._events: dict[str, list[EnergyEvent]] = defaultdict(list)
        self._notes: dict[str, list[MemoryNote]] = defaultdict(list)
        self._prefs: dict[str, dict[str, Any]] = defaultdict(dict)

    def add_reading(self, site_id: str, reading: EnergyReading) -> None:
        self._readings[site_id].append(reading)
        self._readings[site_id] = self._readings[site_id][-self.max_records:]

    def history(self, site_id: str, asset_id: str, metric: str, start: datetime,
                end: datetime) -> list[EnergyReading]:
        ensure_aware(start); ensure_aware(end)
        return sorted((r for r in self._readings[site_id] if r.asset_id == asset_id
                       and r.metric == Metric(metric) and start <= r.timestamp <= end),
                      key=lambda r: r.timestamp)

    def add_event(self, event: EnergyEvent) -> None:
        self._events[event.site_id].append(event)
        self._events[event.site_id] = self._events[event.site_id][-self.max_records:]

    def events(self, site_id: str) -> list[EnergyEvent]:
        return list(self._events[site_id])

    def remember(self, note: MemoryNote) -> None:
        self._notes[note.site_id].append(note)
        self._notes[note.site_id] = self._notes[note.site_id][-self.max_records:]

    def recall(self, site_id: str, query: str = "") -> list[MemoryNote]:
        return [n for n in self._notes[site_id] if query.lower() in (n.text + " " + n.category).lower()]

    def set_preference(self, site_id: str, key: str, value: Any) -> None:
        if not key:
            raise ValueError("preference key is required")
        self._prefs[site_id][key] = value

    def preferences(self, site_id: str) -> dict[str, Any]:
        return dict(self._prefs[site_id])
