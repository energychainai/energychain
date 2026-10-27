"""Advanced read/analysis/planning tools built upon normalized energy semantics."""
from __future__ import annotations
from collections import Counter
from datetime import datetime
from statistics import fmean
from energychain.connectors import ConnectorRegistry
from energychain.exceptions import PermissionDenied, ValidationError
from energychain.fleets import FleetManager
from energychain.intelligence import simple_average_forecast, detect_outliers
from energychain.memory import EnergyContextBuilder, EnergyMemory
from energychain.models import (AssetKind, EnergyConstraint, Metric, EnergyReading,
                                ensure_aware)
from energychain.planning import (energy_balance, estimate_pv_power,
                                  PlanningSlot, FlexibleLoad, optimize_load_schedule)
from energychain.security import Permission
from .base import ToolRegistry, ToolSpec


def _integrate_power(readings: list[EnergyReading], *, max_gap_seconds: int = 7200) -> float:
    """Trapezoidal integration of instantaneous W to Wh; gaps explicitly rejected."""
    ordered = sorted(readings, key=lambda r: r.timestamp)
    if len(ordered) < 2 or any(r.metric != Metric.POWER_W for r in ordered):
        raise ValidationError("power integration requires >=2 power readings")
    energy = 0.0
    for left, right in zip(ordered, ordered[1:]):
        hours = (right.timestamp-left.timestamp).total_seconds()/3600
        if hours <= 0 or hours*3600 > max_gap_seconds:
            raise ValidationError("irregular power data cannot be safely integrated")
        if left.value < 0 or right.value < 0:
            raise ValidationError("load power readings must be nonnegative")
        energy += (left.value+right.value)/2*hours
    return energy


def install_extended_tools(tools: ToolRegistry, connectors: ConnectorRegistry,
                           memory: EnergyMemory, fleets: FleetManager,
                           context: EnergyContextBuilder) -> None:
    def authorized_asset(site_id: str, asset_id: str):
        connector, asset = connectors.route(asset_id)
        if asset.site_id != site_id:
            raise PermissionDenied("energy asset is outside authorized site")
        return connector, asset

    def fleet_snapshot(*, site_id: str, principal, fleet_id: str, metric: str,
                       max_age_seconds: float = 300) -> dict:
        connectors.site(site_id)
        if site_id not in fleets.site_ids(fleet_id):
            raise PermissionDenied("fleet is not scoped to requested site")
        result = fleets.snapshot(fleet_id, principal, Metric(metric),
                                 max_age_seconds=max_age_seconds)
        return {"fleet_id":result.fleet_id, "observations":result.observations,
                "failures":result.failures, "complete":not result.failures,
                "quality":"partial" if result.failures else "observed"}

    def list_sites(*, site_id: str) -> list[str]:
        connectors.site(site_id)
        return [site_id]

    def consumption_summary(*, site_id: str, asset_id: str, start: datetime, end: datetime,
                            max_gap_seconds: int = 7200) -> dict:
        connector, asset = authorized_asset(site_id, asset_id)
        if asset.kind not in {AssetKind.LOAD, AssetKind.METER}:
            raise ValidationError("consumption summary requires load or meter asset")
        ensure_aware(start)
        ensure_aware(end)
        if end <= start:
            raise ValidationError("invalid history interval")
        data = connector.history(asset_id, Metric.POWER_W, start, end)
        energy = _integrate_power(data, max_gap_seconds=max_gap_seconds)
        return {"asset_id":asset_id, "estimated_energy_wh":round(energy,4),
                "peak_power_w":max(x.value for x in data),
                "mean_observed_power_w":fmean(x.value for x in data),
                "samples":len(data), "coverage_start":min(x.timestamp for x in data).isoformat(),
                "coverage_end":max(x.timestamp for x in data).isoformat(),
                "qualities":dict(Counter(x.quality for x in data)),
                "assumption":"trapezoidal interpolation of observed instantaneous power"}

    def demand_forecast(*, site_id: str, asset_id: str, start: datetime, end: datetime,
                        horizon_hours: int = 24) -> dict:
        connector, asset = authorized_asset(site_id, asset_id)
        if asset.kind not in {AssetKind.LOAD, AssetKind.METER}:
            raise ValidationError("demand forecast requires load/meter")
        ensure_aware(start)
        ensure_aware(end)
        readings = connector.history(asset_id, Metric.POWER_W, start, end)
        values = simple_average_forecast(readings, horizon_hours=horizon_hours)
        return {"forecast_power_w":values, "algorithm":"arithmetic_mean_baseline",
                "training_samples":len(readings), "quality":"estimated",
                "warning":"Not a validated machine-learning forecast"}

    def anomalies(*, site_id: str, asset_id: str, metric: str,
                  start: datetime, end: datetime, threshold: float = 3.0) -> dict:
        connector, _ = authorized_asset(site_id, asset_id)
        ensure_aware(start)
        ensure_aware(end)
        data = connector.history(asset_id, Metric(metric), start, end)
        found = detect_outliers(data, threshold=threshold)
        return {"asset_id":asset_id, "metric":Metric(metric).value,
                "anomalies":found, "count":len(found), "samples":len(data),
                "algorithm":"population_zscore_baseline"}

    def context_retrieval(*, site_id: str, query: str = "", asset_id: str | None = None,
                          metric: str | None = None, limit: int = 10) -> dict:
        connectors.site(site_id)
        if asset_id is not None:
            authorized_asset(site_id, asset_id)
        snapshot = context.build(site_id, query=query, asset_id=asset_id, metric=metric, limit=limit)
        return {"preferences":snapshot.preferences, "episodes":snapshot.episodes,
                "notes":snapshot.notes, "observations":snapshot.observations,
                "retrieved_at":snapshot.retrieved_at.isoformat()}

    def get_events(*, site_id: str) -> list:
        connectors.site(site_id)
        return memory.events(site_id)

    def balance(*, site_id: str, solar_w: float, load_w: float,
                generator_w: float = 0) -> dict:
        connectors.site(site_id)
        result = energy_balance(solar_w, load_w, generator_w)
        return {"surplus_w":result.net_surplus_w, "deficit_w":result.deficit_w,
                "quality":"estimated", "warning":"static instantaneous balance only"}

    def pv_estimate(*, site_id: str, irradiance_w_m2: float,
                    rated_capacity_w: float, performance_ratio: float = .78) -> dict:
        connectors.site(site_id)
        value = estimate_pv_power(irradiance_w_m2, rated_capacity_w,
                                  performance_ratio=performance_ratio)
        return {"power_w":round(value,3), "quality":"estimated",
                "assumptions":{"irradiance":"global horizontal W/m²", "performance_ratio":performance_ratio}}

    def check_constraints(*, site_id: str, values: dict[str,float],
                          limits: list[dict]) -> dict:
        connectors.site(site_id)
        constraints = [EnergyConstraint(**limit) for limit in limits]
        if len({c.key for c in constraints}) != len(constraints):
            raise ValidationError("duplicate constraints")
        if set(values) != {c.key for c in constraints}:
            raise ValidationError("missing or unexpected constraint values")
        verdicts = {c.key:c.check(values[c.key]) for c in constraints}
        return {"valid":all(verdicts.values()), "checks":verdicts}

    def optimize(*, site_id: str, slots: list[dict], jobs: list[dict],
                 max_site_power_w: float) -> dict:
        connectors.site(site_id)
        parsed_slots = [PlanningSlot(datetime.fromisoformat(v["timestamp"]), v["solar_w"],
                                     v["base_load_w"], v["tariff_per_kwh"]) for v in slots]
        parsed_loads = [FlexibleLoad(**j) for j in jobs]
        plan = optimize_load_schedule(parsed_slots, parsed_loads,
                                      max_site_power_w=max_site_power_w)
        return {"starts":plan.starts, "baseline_grid_cost":plan.baseline_grid_cost,
                "optimized_grid_cost":plan.optimized_grid_cost,
                "estimated_savings":plan.estimated_savings,
                "assumptions":plan.assumptions, "quality":"advisory"}

    defs = (
        ("list_sites", Permission.READ, "List current authorized site (no fleet enumeration)", list_sites),
        ("analyze_consumption", Permission.ANALYZE, "Integrate power series with gap validation", consumption_summary),
        ("forecast_demand", Permission.ANALYZE, "Transparent baseline demand forecast", demand_forecast),
        ("detect_anomalies", Permission.ANALYZE, "Detect statistical energy outliers", anomalies),
        ("get_energy_context", Permission.READ, "Retrieve scoped memory and episodes", context_retrieval),
        ("get_energy_events", Permission.READ, "Retrieve scoped energy events", get_events),
        ("calculate_energy_balance", Permission.ANALYZE, "Analyze instantaneous supply versus demand", balance),
        ("estimate_pv_generation", Permission.ANALYZE, "Convert irradiance to estimated panel output", pv_estimate),
        ("check_energy_constraints", Permission.ANALYZE, "Evaluate hard numerical constraints", check_constraints),
        ("optimize_load_schedule", Permission.ANALYZE, "Bounded exact scheduling without physical dispatch", optimize),
    )
    tools.register(ToolSpec("get_fleet_snapshot", "Read all authorized fleet sites with explicit partial failures",
                            Permission.READ, fleet_snapshot, needs_principal=True))
    for name, permission, description, handler in defs:
        tools.register(ToolSpec(name, description, permission, handler))
