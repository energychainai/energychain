"""Dependency-free trace events with bounded, opt-in collection."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from energychain.models import utcnow


@dataclass(frozen=True)
class TraceEvent:
    operation: str
    principal_id: str
    site_id: str
    outcome: str
    timestamp: datetime = field(default_factory=utcnow)
    detail: str = ""
    duration_ms: float | None = None
    correlation_id: str | None = None


class InMemoryTracer:
    def __init__(self, max_events: int = 1000) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        self.max_events = max_events
        self._events: list[TraceEvent] = []
        self._lock = RLock()

    def record(self, event: TraceEvent) -> None:
        with self._lock:
            self._events.append(event)
            self._events = self._events[-self.max_events:]

    def events(self, site_id: str | None = None) -> list[TraceEvent]:
        with self._lock:
            return [e for e in self._events if site_id is None or e.site_id == site_id]
