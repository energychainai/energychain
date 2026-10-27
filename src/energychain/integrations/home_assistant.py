"""Read-only Home Assistant REST state connector, opted-in by developer.

HA's /api/states returns observed state, not proof of physical command success.
This adapter never calls /api/services or a mutation endpoint.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from re import fullmatch
from typing import Callable
from urllib.parse import quote, urlsplit
from energychain.connectors.base import EnergyConnector
from energychain.exceptions import AssetNotFound, UnsupportedCapability, ValidationError
from energychain.integrations.http import get_json
from energychain.models import (EnergyAsset, EnergyReading, EnergySite, Metric,
                                METRIC_UNITS, ensure_aware)


@dataclass(frozen=True)
class HAEntityMapping:
    asset: EnergyAsset
    entity_id: str
    metric: Metric
    source_unit: str

    def __post_init__(self) -> None:
        if not fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", self.entity_id):
            raise ValidationError("invalid Home Assistant entity identifier")
        object.__setattr__(self, "metric", Metric(self.metric))
        if self.source_unit not in {METRIC_UNITS[self.metric], "kW", "kWh"}:
            raise ValidationError("unsupported or ambiguous Home Assistant unit mapping")
        if self.source_unit == "kW" and self.metric != Metric.POWER_W:
            raise ValidationError("kW is only valid for power measurements")
        if self.source_unit == "kWh" and self.metric not in {Metric.ENERGY_WH, Metric.CAPACITY_WH}:
            raise ValidationError("kWh only valid for energy measurements")


class HomeAssistantConnector(EnergyConnector):
    def __init__(self, *, site: EnergySite, mappings: list[HAEntityMapping],
                 base_url: str, token_provider: Callable[[], str],
                 transport: Callable[..., object] = get_json) -> None:
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValidationError("Home Assistant base URL must be HTTPS origin (use TLS reverse proxy)")
        if not mappings or any(m.asset.site_id != site.id for m in mappings):
            raise ValidationError("all entity mappings must belong to registered site")
        pairs = [(m.asset.id, m.metric) for m in mappings]
        if len(pairs) != len(set(pairs)):
            raise ValidationError("duplicate entity mapping for asset and metric")
        self._site = site
        self._maps = {(m.asset.id, m.metric): m for m in mappings}
        self._assets = {m.asset.id: m.asset for m in mappings}
        self._base = base_url.rstrip("/")
        self._token_provider = token_provider
        self._transport = transport

    def sites(self) -> list[EnergySite]:
        return [self._site]

    def assets(self, site_id: str) -> list[EnergyAsset]:
        return list(self._assets.values()) if site_id == self._site.id else []

    def read(self, asset_id: str, metric: Metric) -> EnergyReading:
        try:
            mapping = self._maps[(asset_id, Metric(metric))]
        except KeyError as exc:
            raise AssetNotFound("unmapped energy asset metric") from exc
        token = self._token_provider()
        if not isinstance(token, str) or not token:
            raise ValidationError("Home Assistant credentials are not configured")
        payload = self._transport(
            f"{self._base}/api/states/{quote(mapping.entity_id, safe='.')}", token=token)
        if not isinstance(payload, dict) or payload.get("entity_id") != mapping.entity_id:
            raise ValidationError("Home Assistant response entity mismatch")
        attrs = payload.get("attributes")
        if not isinstance(attrs, dict) or attrs.get("unit_of_measurement") != mapping.source_unit:
            raise ValidationError("Home Assistant observation unit mismatch")
        try:
            value = float(payload["state"])
            stamp = datetime.fromisoformat(payload["last_updated"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("missing or nonnumeric Home Assistant observation") from exc
        ensure_aware(stamp)
        if not isfinite(value):
            raise ValidationError("nonfinite Home Assistant observation")
        if mapping.source_unit in {"kW", "kWh"}:
            value *= 1000
        return EnergyReading(asset_id, mapping.metric, value, stamp,
                             source="home-assistant", quality="measured",
                             metadata={"entity_id": mapping.entity_id})

    def history(self, asset_id: str, metric: Metric, start: datetime, end: datetime) -> list[EnergyReading]:
        raise UnsupportedCapability("HA historical observations are not provided by this read-only adapter")
