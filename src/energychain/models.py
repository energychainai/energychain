"""Vendor-neutral energy domain data types and invariants.

Everything uses SI units. Time stamps must be timezone-aware. Power in W, energy in Wh,
state-of-charge in %, and currency is always explicit rather than silently presumed.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any
from .exceptions import ValidationError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(ts: datetime) -> None:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValidationError("timestamp must include a timezone")


class AssetKind(str, Enum):
    SOLAR = "solar"
    BATTERY = "battery"
    METER = "meter"
    LOAD = "load"
    INVERTER = "inverter"
    GENERATOR = "generator"
    OTHER = "other"


class Capability(str, Enum):
    READ = "read"
    HISTORY = "history"
    EXECUTE = "execute"


class Metric(str, Enum):
    POWER_W = "power_w"
    ENERGY_WH = "energy_wh"
    STATE_OF_CHARGE_PCT = "state_of_charge_pct"
    CAPACITY_WH = "capacity_wh"
    VOLTAGE_V = "voltage_v"
    CURRENT_A = "current_a"
    FREQUENCY_HZ = "frequency_hz"
    TEMPERATURE_C = "temperature_c"


METRIC_UNITS = {
    Metric.POWER_W: "W", Metric.ENERGY_WH: "Wh", Metric.STATE_OF_CHARGE_PCT: "%",
    Metric.CAPACITY_WH: "Wh", Metric.VOLTAGE_V: "V", Metric.CURRENT_A: "A",
    Metric.FREQUENCY_HZ: "Hz", Metric.TEMPERATURE_C: "°C",
}


@dataclass(frozen=True)
class EnergySite:
    id: str
    name: str
    timezone_name: str = "UTC"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValidationError("site id and name are required")


@dataclass(frozen=True)
class EnergyAsset:
    id: str
    site_id: str
    name: str
    kind: AssetKind
    capabilities: frozenset[Capability] = frozenset({Capability.READ})
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.site_id.strip() or not self.name.strip():
            raise ValidationError("asset id, site id and name are required")
        object.__setattr__(self, "kind", AssetKind(self.kind))
        object.__setattr__(self, "capabilities", frozenset(Capability(c) for c in self.capabilities))


@dataclass(frozen=True)
class EnergyReading:
    asset_id: str
    metric: Metric
    value: float
    timestamp: datetime
    source: str
    quality: str = "measured"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric", Metric(self.metric))
        if not self.asset_id or not self.source:
            raise ValidationError("asset id and source are required")
        ensure_aware(self.timestamp)
        if not isfinite(self.value):
            raise ValidationError("reading value must be finite")
        if self.metric == Metric.STATE_OF_CHARGE_PCT and not 0 <= self.value <= 100:
            raise ValidationError("state of charge must be between 0 and 100")
        if self.metric == Metric.CAPACITY_WH and self.value < 0:
            raise ValidationError("capacity must not be negative")
        if self.quality not in {"measured", "estimated", "simulated"}:
            raise ValidationError("invalid reading quality")

    @property
    def unit(self) -> str:
        return METRIC_UNITS[self.metric]


@dataclass(frozen=True)
class EnergyEvent:
    id: str
    site_id: str
    category: str
    message: str
    timestamp: datetime = field(default_factory=utcnow)
    asset_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ensure_aware(self.timestamp)
        if not self.id or not self.site_id or not self.category:
            raise ValidationError("event id, site id and category are required")


@dataclass(frozen=True)
class Tariff:
    price_per_kwh: float
    currency: str = "NGN"

    def __post_init__(self) -> None:
        if not isfinite(self.price_per_kwh) or self.price_per_kwh < 0:
            raise ValidationError("price per kWh must be finite and non-negative")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValidationError("currency must be a three-letter ISO code")


@dataclass(frozen=True)
class EnergyPlan:
    site_id: str
    summary: str
    recommendations: tuple[str, ...]
    estimated: bool = True
    warnings: tuple[str, ...] = ()
