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


class RelationshipKind(str, Enum):
    """Logical relationships only; does not imply controllability."""
    FEEDS = "feeds"
    MEASURES = "measures"
    STORES_FROM = "stores_from"
    BACKS_UP = "backs_up"


@dataclass(frozen=True)
class EnergyRelationship:
    site_id: str
    source_asset_id: str
    destination_asset_id: str
    kind: RelationshipKind

    def __post_init__(self) -> None:
        if not self.site_id or not self.source_asset_id or not self.destination_asset_id:
            raise ValidationError("relationship identifiers are required")
        if self.source_asset_id == self.destination_asset_id:
            raise ValidationError("self-referential relationships are not allowed")
        object.__setattr__(self, "kind", RelationshipKind(self.kind))


@dataclass(frozen=True)
class EnergyTopology:
    """Site-local graph validated against the registered asset catalogue."""
    site_id: str
    relationships: tuple[EnergyRelationship, ...]

    def validate(self, assets: list[EnergyAsset]) -> None:
        known = {a.id for a in assets if a.site_id == self.site_id}
        if len(known) != len([a for a in assets if a.site_id == self.site_id]):
            raise ValidationError("duplicate topology asset identifiers")
        for relation in self.relationships:
            if relation.site_id != self.site_id or not {
                relation.source_asset_id, relation.destination_asset_id
            }.issubset(known):
                raise ValidationError("topology relationship crosses sites or references missing asset")
        if len(set(self.relationships)) != len(self.relationships):
            raise ValidationError("duplicate topology relationship")


@dataclass(frozen=True)
class EnergyConstraint:
    """Hard, numerical constraint for planning; independent of LLM output."""
    key: str
    lower: float | None = None
    upper: float | None = None
    unit: str = ""

    def __post_init__(self) -> None:
        if not self.key or (self.lower is None and self.upper is None):
            raise ValidationError("constraint requires key and bound")
        if any(not isfinite(x) for x in (self.lower, self.upper) if x is not None):
            raise ValidationError("constraint bounds must be finite")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValidationError("constraint lower bound exceeds upper bound")

    def check(self, value: float) -> bool:
        return (isinstance(value, (int, float)) and not isinstance(value, bool) and
                isfinite(value) and (self.lower is None or value >= self.lower) and (
            self.upper is None or value <= self.upper))


@dataclass(frozen=True)
class EnergyActionSpec:
    """Declared *potential* capability; neither authorization nor execution."""
    asset_id: str
    command: str
    parameter_bounds: tuple[EnergyConstraint, ...] = ()
    human_approval_required: bool = True

    def __post_init__(self) -> None:
        if not self.asset_id or not self.command:
            raise ValidationError("asset id and command are required")
        if len({x.key for x in self.parameter_bounds}) != len(self.parameter_bounds):
            raise ValidationError("duplicate action parameter constraint")

    def validate(self, parameters: dict[str, float]) -> None:
        expected = {x.key for x in self.parameter_bounds}
        if set(parameters) != expected:
            raise ValidationError("action parameters do not match declared bounded parameters")
        if not all(x.check(parameters[x.key]) for x in self.parameter_bounds):
            raise ValidationError("action parameters exceed declared bounds")


def require_fresh(reading: EnergyReading, *, maximum_age_seconds: float,
                  now: datetime | None = None) -> None:
    """Reject future, stale or incorrectly clocked readings for operational decisions."""
    from .exceptions import StaleReading
    reference = now or utcnow()
    ensure_aware(reference)
    if not isfinite(maximum_age_seconds) or maximum_age_seconds <= 0:
        raise ValidationError("maximum age must be finite and positive")
    age = (reference - reading.timestamp).total_seconds()
    if age < -30 or age > maximum_age_seconds:
        raise StaleReading(f"{reading.asset_id}/{reading.metric.value} reading is outside freshness window")
