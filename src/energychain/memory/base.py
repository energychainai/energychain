"""Memory contract and site-scoped records."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from energychain.models import EnergyReading, EnergyEvent, utcnow, ensure_aware


@dataclass(frozen=True)
class MemoryNote:
    site_id: str
    category: str
    text: str
    timestamp: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        ensure_aware(self.timestamp)


class EnergyMemory(ABC):
    @abstractmethod
    def add_reading(self, site_id: str, reading: EnergyReading) -> None: ...
    @abstractmethod
    def history(self, site_id: str, asset_id: str, metric: str, start: datetime,
                end: datetime) -> list[EnergyReading]: ...
    @abstractmethod
    def add_event(self, event: EnergyEvent) -> None: ...
    @abstractmethod
    def events(self, site_id: str) -> list[EnergyEvent]: ...
    @abstractmethod
    def remember(self, note: MemoryNote) -> None: ...
    @abstractmethod
    def recall(self, site_id: str, query: str = "") -> list[MemoryNote]: ...
    @abstractmethod
    def set_preference(self, site_id: str, key: str, value: Any) -> None: ...
    @abstractmethod
    def preferences(self, site_id: str) -> dict[str, Any]: ...
