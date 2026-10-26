"""Deterministic, read-only hybrid-power simulator. No external hardware controls."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from math import pi, sin
from energychain.connectors.base import EnergyConnector
from energychain.exceptions import AssetNotFound, ValidationError
from energychain.models import (AssetKind, Capability, EnergyAsset, EnergyReading,
                               EnergySite, Metric, ensure_aware, utcnow)


class HybridSiteSimulator(EnergyConnector):
    """Synthetic solar/battery/load/generator readings, reproducible at a given timestamp.

    Designed for developer demos, not for billing, equipment protection or actual energy dispatch.
    """
    def __init__(self, *, site_id: str = "demo-site", clock=None) -> None:
        self.site = EnergySite(site_id, "Example hybrid site", "UTC")
        self.clock = clock or utcnow
        prefix = "demo-" if site_id == "demo-site" else f"{site_id}-"
        self._prefix = prefix
        self._assets = [
            EnergyAsset(prefix + "solar", site_id, "Rooftop solar", AssetKind.SOLAR, frozenset({Capability.READ, Capability.HISTORY})),
            EnergyAsset(prefix + "battery", site_id, "Storage bank", AssetKind.BATTERY, frozenset({Capability.READ, Capability.HISTORY})),
            EnergyAsset(prefix + "load", site_id, "Office loads", AssetKind.LOAD, frozenset({Capability.READ, Capability.HISTORY})),
            EnergyAsset(prefix + "generator", site_id, "Backup generator", AssetKind.GENERATOR, frozenset({Capability.READ, Capability.HISTORY})),
        ]

    def sites(self) -> list[EnergySite]:
        return [self.site]

    def assets(self, site_id: str) -> list[EnergyAsset]:
        return list(self._assets) if site_id == self.site.id else []

    def _value(self, asset_id: str, metric: Metric, ts: datetime) -> float:
        hour = ts.astimezone(timezone.utc).hour + ts.minute / 60
        sun = max(0.0, sin(pi * (hour - 6) / 12))
        values = {
            (self._prefix + "solar", Metric.POWER_W): round(3800 * sun, 2),
            (self._prefix + "battery", Metric.STATE_OF_CHARGE_PCT): round(max(16.0, min(98.0, 55 + 20 * sun - 0.5 * hour)), 2),
            (self._prefix + "battery", Metric.CAPACITY_WH): 10000.0,
            (self._prefix + "load", Metric.POWER_W): 900.0 if hour < 8 or hour > 18 else 1650.0,
            (self._prefix + "generator", Metric.POWER_W): 0.0,
        }
        try:
            return values[(asset_id, metric)]
        except KeyError as exc:
            raise ValidationError(f"unsupported metric {metric} for {asset_id}") from exc

    def read(self, asset_id: str, metric: Metric) -> EnergyReading:
        if asset_id not in {a.id for a in self._assets}:
            raise AssetNotFound(asset_id)
        ts = self.clock()
        ensure_aware(ts)
        return EnergyReading(asset_id, Metric(metric), self._value(asset_id, Metric(metric), ts), ts, "hybrid-simulator", "simulated")

    def history(self, asset_id: str, metric: Metric, start: datetime, end: datetime) -> list[EnergyReading]:
        ensure_aware(start); ensure_aware(end)
        if end < start:
            raise ValidationError("end precedes start")
        if (end - start).total_seconds() > 31 * 86400:
            raise ValidationError("simulator history limited to 31 days per request")
        if asset_id not in {a.id for a in self._assets}:
            raise AssetNotFound(asset_id)
        result = []
        ts = start
        while ts <= end:
            result.append(EnergyReading(asset_id, Metric(metric), self._value(asset_id, Metric(metric), ts), ts, "hybrid-simulator", "simulated"))
            ts += timedelta(hours=1)
        return result
