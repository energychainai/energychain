"""Deterministic energy calculations with explicit units and conservative assumptions."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from statistics import fmean
from energychain.exceptions import ValidationError
from energychain.models import EnergyReading, Tariff


def _nonnegative(label: str, value: float) -> None:
    if not isfinite(value) or value < 0:
        raise ValidationError(f"{label} must be a finite, non-negative number")


@dataclass(frozen=True)
class RuntimeEstimate:
    hours: float | None
    usable_energy_wh: float
    assumptions: tuple[str, ...]


def estimate_battery_runtime(capacity_wh: float, state_of_charge_pct: float,
                             load_w: float, *, reserve_pct: float = 20.0,
                             discharge_efficiency: float = 0.9) -> RuntimeEstimate:
    """Simple fixed-load battery runtime approximation, not an equipment safety guarantee."""
    for key, val in [("capacity_wh", capacity_wh), ("load_w", load_w)]:
        _nonnegative(key, val)
    if not 0 <= state_of_charge_pct <= 100 or not isfinite(state_of_charge_pct):
        raise ValidationError("state_of_charge_pct must be within [0, 100]")
    if not 0 <= reserve_pct <= 100 or not isfinite(reserve_pct):
        raise ValidationError("reserve_pct must be within [0, 100]")
    if not 0 < discharge_efficiency <= 1 or not isfinite(discharge_efficiency):
        raise ValidationError("efficiency must be within (0, 1]")
    usable = capacity_wh * max(0.0, state_of_charge_pct - reserve_pct) / 100 * discharge_efficiency
    return RuntimeEstimate(hours=None if load_w == 0 else usable / load_w,
                           usable_energy_wh=usable,
                           assumptions=("constant load", "constant efficiency", "no future charging", "battery capacity assumed usable"))


def estimate_energy_cost(energy_wh: float, tariff: Tariff) -> float:
    _nonnegative("energy_wh", energy_wh)
    return round((energy_wh / 1000) * tariff.price_per_kwh, 4)


def simple_average_forecast(readings: list[EnergyReading], horizon_hours: int = 24) -> list[float]:
    """Transparent baseline forecast; NOT a trained forecasting model."""
    if not 1 <= horizon_hours <= 168:
        raise ValidationError("forecast horizon must be within 1..168 hours")
    if not readings:
        raise ValidationError("forecast requires historical readings")
    if len({r.metric for r in readings}) != 1:
        raise ValidationError("forecast readings must share one metric")
    avg = fmean(r.value for r in readings)
    return [avg] * horizon_hours


def detect_outliers(readings: list[EnergyReading], *, threshold: float = 3.0) -> list[EnergyReading]:
    """Simple z-score anomaly baseline; returns no anomalies for zero-variance data."""
    from statistics import pstdev
    if threshold <= 0 or not isfinite(threshold):
        raise ValidationError("threshold must be positive")
    if len(readings) < 3:
        return []
    if len({r.metric for r in readings}) != 1:
        raise ValidationError("readings must share one metric")
    mean = fmean(r.value for r in readings)
    std = pstdev(r.value for r in readings)
    return [] if std == 0 else [r for r in readings if abs(r.value - mean) > threshold * std]
