"""Validated energy telemetry ingestion and a bounded in-process event bus.

This is an SDK-level ingestion boundary, not a durable streaming broker or high-volume collector.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from threading import RLock
from typing import Callable
from energychain.connectors import ConnectorRegistry
from energychain.exceptions import PermissionDenied, ValidationError
from energychain.memory import EnergyMemory
from energychain.models import EnergyReading, EnergyEvent, require_fresh


@dataclass(frozen=True)
class IngestionReceipt:
    source_event_id: str
    site_id: str
    asset_id: str
    accepted: bool
    duplicate: bool


class TelemetryIngestor:
    """Idempotency within process. Call only after trusted connector authentication."""
    def __init__(self, connectors: ConnectorRegistry, memory: EnergyMemory,
                 *, accepted_age_seconds: float = 7*86400, max_ids: int = 50_000) -> None:
        if max_ids <= 0:
            raise ValidationError("max_ids must be positive")
        self.connectors, self.memory = connectors, memory
        self.age_seconds = accepted_age_seconds
        self._ids: set[tuple[str, str]] = set()
        self._order: deque[tuple[str,str]] = deque()
        self._limit = max_ids
        self._lock = RLock()

    def ingest(self, site_id: str, reading: EnergyReading, *,
               source_event_id: str) -> IngestionReceipt:
        if not source_event_id or len(source_event_id) > 256:
            raise ValidationError("source event id required and bounded")
        _, asset = self.connectors.route(reading.asset_id)
        if asset.site_id != site_id:
            raise PermissionDenied("ingested reading crosses site boundary")
        require_fresh(reading, maximum_age_seconds=self.age_seconds)
        key = (site_id, source_event_id)
        with self._lock:
            if key in self._ids:
                return IngestionReceipt(source_event_id, site_id, reading.asset_id, False, True)
            self.memory.add_reading(site_id, reading)
            self._ids.add(key)
            self._order.append(key)
            if len(self._order) > self._limit:
                self._ids.remove(self._order.popleft())
        return IngestionReceipt(source_event_id, site_id, reading.asset_id, True, False)


class EnergyEventBus:
    """Synchronous, bounded local pub/sub; subscribers must be trusted and nonblocking."""
    def __init__(self, *, max_events: int = 1000):
        if max_events <= 0:
            raise ValidationError("max_events must be positive")
        self._events: deque[EnergyEvent] = deque(maxlen=max_events)
        self._listeners: dict[int, Callable[[EnergyEvent], None]] = {}
        self._counter = 0
        self._lock = RLock()

    def subscribe(self, listener: Callable[[EnergyEvent], None]) -> int:
        with self._lock:
            self._counter += 1
            self._listeners[self._counter] = listener
            return self._counter

    def unsubscribe(self, ident: int) -> None:
        with self._lock:
            self._listeners.pop(ident, None)

    def publish(self, event: EnergyEvent) -> int:
        with self._lock:
            self._events.append(event)
            listeners = tuple(self._listeners.values())
        delivered = 0
        for fn in listeners:
            try:
                fn(event)
                delivered += 1
            except Exception:
                # A faulty subscriber must not disable event recording.
                pass
        return delivered

    def recent(self, site_id: str) -> list[EnergyEvent]:
        with self._lock:
            return [e for e in self._events if e.site_id == site_id]
