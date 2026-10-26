"""Read-only connector for existing telemetry exported as CSV.

Columns: asset_id,metric,value,timestamp,source. Timestamps require ISO-8601 timezone.
This is useful for integrating datasets without credentials or vendor-specific APIs.
"""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
from energychain.connectors.base import EnergyConnector
from energychain.exceptions import AssetNotFound, ValidationError
from energychain.models import (AssetKind, Capability, EnergyAsset, EnergyReading,
                               EnergySite, Metric, ensure_aware)


class CSVConnector(EnergyConnector):
    def __init__(self, *, site: EnergySite, assets: list[EnergyAsset],
                 records: list[EnergyReading]) -> None:
        if any(a.site_id != site.id for a in assets):
            raise ValidationError("all assets must belong to CSV site")
        ids = [a.id for a in assets]
        if len(set(ids)) != len(ids):
            raise ValidationError("duplicate CSV asset id")
        if any(r.asset_id not in ids for r in records):
            raise ValidationError("CSV records reference unregistered assets")
        self.site = site
        self._assets = list(assets)
        self._records = sorted(records, key=lambda r: r.timestamp)

    @classmethod
    def from_csv(cls, path: str | Path, *, site: EnergySite,
                 assets: list[EnergyAsset]) -> "CSVConnector":
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            needed = {"asset_id", "metric", "value", "timestamp", "source"}
            if not needed.issubset(reader.fieldnames or []):
                raise ValidationError(f"CSV missing required columns: {sorted(needed)}")
            records = []
            for i, row in enumerate(reader, start=2):
                try:
                    records.append(EnergyReading(
                        asset_id=row["asset_id"], metric=Metric(row["metric"]),
                        value=float(row["value"]), timestamp=datetime.fromisoformat(row["timestamp"]),
                        source=row["source"], quality=row.get("quality") or "measured"))
                except (ValueError, TypeError, KeyError) as exc:
                    raise ValidationError(f"invalid energy CSV row {i}: {exc}") from exc
        return cls(site=site, assets=assets, records=records)

    def sites(self) -> list[EnergySite]:
        return [self.site]

    def assets(self, site_id: str) -> list[EnergyAsset]:
        return list(self._assets) if site_id == self.site.id else []

    def read(self, asset_id: str, metric: Metric) -> EnergyReading:
        if asset_id not in {a.id for a in self._assets}:
            raise AssetNotFound(asset_id)
        results = [r for r in self._records if r.asset_id == asset_id and r.metric == Metric(metric)]
        if not results:
            raise AssetNotFound(f"metric not present for {asset_id}: {metric}")
        return results[-1]

    def history(self, asset_id: str, metric: Metric, start: datetime, end: datetime) -> list[EnergyReading]:
        ensure_aware(start); ensure_aware(end)
        if asset_id not in {a.id for a in self._assets}:
            raise AssetNotFound(asset_id)
        if end < start:
            raise ValidationError("end precedes start")
        return [r for r in self._records if r.asset_id == asset_id and r.metric == Metric(metric)
                and start <= r.timestamp <= end]
