"""Structured energy episodes: traceable events and outcomes, not chat transcripts.

The SQLite backend is suitable for single-user or trusted on-prem deployments only.
Cross-tenant authorization must be enforced by the application service.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import json
import sqlite3
from pathlib import Path
from typing import Protocol
from energychain.models import ensure_aware, utcnow
from energychain.exceptions import ValidationError


@dataclass(frozen=True)
class EnergyEpisode:
    id: str
    site_id: str
    category: str
    summary: str
    observed_at: datetime = field(default_factory=utcnow)
    asset_ids: tuple[str, ...] = ()
    outcome: str = "unknown"
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.id, self.site_id, self.category, self.summary)):
            raise ValidationError("episode identifiers, category and summary are required")
        ensure_aware(self.observed_at)
        if len(self.summary) > 8192 or len(self.evidence) > 100:
            raise ValidationError("episode exceeds bounded memory limits")


class EpisodeStore(Protocol):
    def add(self, episode: EnergyEpisode) -> None: ...
    def recall(self, site_id: str, query: str = "", limit: int = 20) -> list[EnergyEpisode]: ...
    def delete_site(self, site_id: str) -> None: ...


class InMemoryEpisodeStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], EnergyEpisode] = {}

    def add(self, episode: EnergyEpisode) -> None:
        key = (episode.site_id, episode.id)
        if key in self._items:
            raise ValidationError("duplicate episode")
        self._items[key] = episode

    def recall(self, site_id: str, query: str = "", limit: int = 20) -> list[EnergyEpisode]:
        _check_limit(limit)
        matches = (e for e in self._items.values() if e.site_id == site_id and
                   query.casefold() in f"{e.category} {e.summary} {e.outcome}".casefold())
        return sorted(matches, key=lambda e: e.observed_at, reverse=True)[:limit]

    def delete_site(self, site_id: str) -> None:
        for key in list(self._items):
            if key[0] == site_id:
                del self._items[key]


def _check_limit(limit: int) -> None:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValidationError("episode retrieval limit must be 1..100")


class SQLiteEpisodeStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path))
        self._db.execute("""CREATE TABLE IF NOT EXISTS episodes (
            site TEXT NOT NULL, id TEXT NOT NULL, category TEXT NOT NULL,
            summary TEXT NOT NULL, observed TEXT NOT NULL, asset_ids TEXT NOT NULL,
            outcome TEXT NOT NULL, evidence TEXT NOT NULL,
            PRIMARY KEY(site,id))""")
        self._db.execute("CREATE INDEX IF NOT EXISTS episodes_time ON episodes(site, observed)")
        self._db.commit()

    def add(self, episode: EnergyEpisode) -> None:
        try:
            with self._db:
                self._db.execute("INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?)", (
                    episode.site_id, episode.id, episode.category, episode.summary,
                    episode.observed_at.isoformat(), json.dumps(episode.asset_ids),
                    episode.outcome, json.dumps(episode.evidence)))
        except sqlite3.IntegrityError as exc:
            raise ValidationError("duplicate episode") from exc

    def recall(self, site_id: str, query: str = "", limit: int = 20) -> list[EnergyEpisode]:
        _check_limit(limit)
        # Avoid SQL LIKE wildcard semantics: literal, case-insensitive substring match.
        rows = self._db.execute("SELECT id,category,summary,observed,asset_ids,outcome,evidence "
                                "FROM episodes WHERE site=? ORDER BY observed DESC", (site_id,)).fetchall()
        result = []
        for ident, cat, summary, ts, assets, outcome, evidence in rows:
            if query.casefold() in (cat+" "+summary+" "+outcome).casefold():
                result.append(EnergyEpisode(ident, site_id, cat, summary, datetime.fromisoformat(ts),
                                            tuple(json.loads(assets)), outcome,
                                            tuple(json.loads(evidence))))
            if len(result) >= limit:
                break
        return result

    def delete_site(self, site_id: str) -> None:
        with self._db:
            self._db.execute("DELETE FROM episodes WHERE site=?", (site_id,))

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "SQLiteEpisodeStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
