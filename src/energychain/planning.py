"""Deterministic advisory planning with explicit electrical and financial assumptions.

No device commands are generated. Results must be reviewed against actual inverter, battery,
site wiring and user constraints by a qualified operator before action.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from math import isfinite
from energychain.exceptions import ValidationError
from energychain.models import ensure_aware


@dataclass(frozen=True)
class EnergyBalance:
    solar_w: float
    load_w: float
    generator_w: float
    net_surplus_w: float
    deficit_w: float
    quality: str = "estimated"


def energy_balance(solar_w: float, load_w: float, generator_w: float = 0) -> EnergyBalance:
    for n in (solar_w, load_w, generator_w):
        if not isfinite(n) or n < 0:
            raise ValidationError("energy balance requires finite nonnegative power")
    net = solar_w + generator_w - load_w
    return EnergyBalance(solar_w, load_w, generator_w, max(net,0), max(-net,0))


def estimate_pv_power(irradiance_w_m2: float, rated_capacity_w: float,
                      *, performance_ratio: float = 0.78) -> float:
    """Approximate PV output at STC 1000 W/m², without clipping to inverter rating."""
    if (not all(isfinite(x) for x in (irradiance_w_m2, rated_capacity_w, performance_ratio))
        or irradiance_w_m2 < 0 or rated_capacity_w < 0
        or not 0 < performance_ratio <= 1):
        raise ValidationError("invalid PV estimation parameters")
    return irradiance_w_m2/1000 * rated_capacity_w * performance_ratio


@dataclass(frozen=True)
class PlanningSlot:
    timestamp: datetime
    solar_w: float
    base_load_w: float
    tariff_per_kwh: float

    def __post_init__(self):
        ensure_aware(self.timestamp)
        if any(not isfinite(x) or x < 0 for x in
               (self.solar_w, self.base_load_w, self.tariff_per_kwh)):
            raise ValidationError("planning slots require nonnegative finite inputs")


@dataclass(frozen=True)
class FlexibleLoad:
    id: str
    power_w: float
    duration_slots: int
    earliest_start: int
    latest_end: int

    def __post_init__(self):
        if (not self.id or not isfinite(self.power_w) or self.power_w <= 0 or
            not isinstance(self.duration_slots, int) or self.duration_slots <= 0 or
            not 0 <= self.earliest_start < self.latest_end or
            self.earliest_start + self.duration_slots > self.latest_end):
            raise ValidationError("invalid flexible load")


@dataclass(frozen=True)
class AdvisoryLoadPlan:
    starts: dict[str, int]
    baseline_grid_cost: float
    optimized_grid_cost: float
    estimated_savings: float
    evaluated_schedules: int
    assumptions: tuple[str, ...] = (
        "hourly constant average power", "no battery dispatch modeled",
        "no export compensation", "grid import allowed", "advisory plan only")


def optimize_load_schedule(slots: list[PlanningSlot], loads: list[FlexibleLoad], *,
                           max_site_power_w: float, max_evaluations: int = 100_000) -> AdvisoryLoadPlan:
    """Exact enumeration within bounded search; rejects incomplete searches rather than claim optimality.

    A plan is feasible when total instantaneous modeled site load <= max_site_power_w.
    Solar offsets site load. Remaining demand is assumed metered grid import.
    """
    if (not slots or len(slots) > 48 or len(loads) > 7 or
        not isfinite(max_site_power_w) or max_site_power_w <= 0 or
        max_evaluations < 1):
        raise ValidationError("schedule exceeds supported bounded problem size")
    if len({x.id for x in loads}) != len(loads):
        raise ValidationError("duplicate flexible load identifier")
    if any(s.base_load_w > max_site_power_w for s in slots):
        raise ValidationError("base load already exceeds site power cap")
    if any(slots[i].timestamp >= slots[i+1].timestamp for i in range(len(slots)-1)):
        raise ValidationError("planning slots must have ascending timestamps")
    # Exactly one-hour slot interval, required by price and power-to-energy conversion.
    if any((slots[i+1].timestamp - slots[i].timestamp).total_seconds() != 3600
           for i in range(len(slots)-1)):
        raise ValidationError("planning slots must be hourly")
    if any(load.latest_end > len(slots) for load in loads):
        raise ValidationError("load deadline exceeds horizon")
    candidates = [range(j.earliest_start, j.latest_end-j.duration_slots+1) for j in loads]
    combinations = 1
    for c in candidates:
        combinations *= len(c)
    if combinations > max_evaluations:
        raise ValidationError("schedule combinatorial search exceeds safe bound")

    def cost(starts: tuple[int,...]) -> float | None:
        consumption = [slot.base_load_w for slot in slots]
        for job, start in zip(loads, starts):
            for t in range(start, start+job.duration_slots):
                consumption[t] += job.power_w
                if consumption[t] > max_site_power_w:
                    return None
        return sum(max(0, total - slot.solar_w) / 1000 * slot.tariff_per_kwh
                   for total, slot in zip(consumption, slots))

    # Baseline is all loads at earliest feasible start, even when this violates site cap.
    # If invalid, we report no meaningful baseline (0 savings by convention).
    baseline = cost(tuple(j.earliest_start for j in loads))
    best_cost = None
    best_starts: tuple[int,...] = ()
    evaluated = 0
    for starts in product(*candidates):
        evaluated += 1
        amount = cost(starts)
        if amount is not None and (best_cost is None or amount < best_cost):
            best_cost, best_starts = amount, starts
    if best_cost is None:
        raise ValidationError("no feasible schedule within declared constraints")
    initial = baseline if baseline is not None else best_cost
    return AdvisoryLoadPlan({job.id: start for job, start in zip(loads, best_starts)},
                            round(initial, 4), round(best_cost, 4),
                            round(max(0, initial-best_cost),4), evaluated)
