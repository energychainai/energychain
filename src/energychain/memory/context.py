"""Explicit site-scoped context assembly; no hallucinated numerical summaries."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from energychain.memory.base import EnergyMemory, MemoryNote
from energychain.memory.episodes import EpisodeStore, EnergyEpisode
from energychain.models import EnergyReading, ensure_aware, utcnow
from energychain.exceptions import ValidationError


@dataclass(frozen=True)
class EnergyContext:
    site_id: str
    query: str
    preferences: dict
    episodes: tuple[EnergyEpisode, ...]
    notes: tuple[MemoryNote, ...]
    observations: tuple[EnergyReading, ...]
    retrieved_at: datetime


class EnergyContextBuilder:
    def __init__(self, memory: EnergyMemory, episodes: EpisodeStore) -> None:
        self.memory = memory
        self.episodes = episodes

    def build(self, site_id: str, *, query: str = "", asset_id: str | None = None,
              metric: str | None = None, observation_window_hours: int = 24,
              limit: int = 20, now: datetime | None = None) -> EnergyContext:
        if not site_id or not 1 <= observation_window_hours <= 24*90 or not 1 <= limit <= 100:
            raise ValidationError("invalid context scope or limits")
        stamp = now or utcnow()
        ensure_aware(stamp)
        observations = ()
        if asset_id is not None or metric is not None:
            if not asset_id or not metric:
                raise ValidationError("both asset_id and metric are required for context observations")
            observations = tuple(self.memory.history(site_id, asset_id, metric,
                                stamp-timedelta(hours=observation_window_hours), stamp)[-limit:])
        return EnergyContext(site_id, query, self.memory.preferences(site_id),
                             tuple(self.episodes.recall(site_id, query, limit)),
                             tuple(self.memory.recall(site_id, query)[-limit:]),
                             observations, stamp)
