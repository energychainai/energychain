"""Ready-to-use read and analytics tools; no physical execution tools in v0.1."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from energychain.connectors import ConnectorRegistry
from energychain.exceptions import PermissionDenied, ValidationError
from energychain.intelligence import estimate_battery_runtime, estimate_energy_cost
from energychain.memory import EnergyMemory
from energychain.models import AssetKind, EnergyAsset, EnergyReading, Metric, Tariff
from energychain.security import Permission
from .base import ToolRegistry, ToolSpec


def install_builtin_tools(tools: ToolRegistry, connectors: ConnectorRegistry,
                          memory: EnergyMemory) -> None:
    def route(site_id: str, asset_id: str) -> tuple[Any, EnergyAsset]:
        connector, asset = connectors.route(asset_id)
        if asset.site_id != site_id:
            raise PermissionDenied("asset is outside the authorized site")
        return connector, asset

    def discover_assets(*, site_id: str) -> list[EnergyAsset]:
        connectors.site(site_id)
        return connectors.assets(site_id)

    def get_asset_state(*, site_id: str, asset_id: str, metric: str) -> EnergyReading:
        connector, _ = route(site_id, asset_id)
        reading = connector.read(asset_id, Metric(metric))
        memory.add_reading(site_id, reading)
        return reading

    def get_energy_history(*, site_id: str, asset_id: str, metric: str,
                           start: datetime, end: datetime) -> list[EnergyReading]:
        connector, _ = route(site_id, asset_id)
        return connector.history(asset_id, Metric(metric), start, end)

    def get_battery_state(*, site_id: str, asset_id: str) -> dict[str, EnergyReading]:
        connector, asset = route(site_id, asset_id)
        if asset.kind != AssetKind.BATTERY:
            raise ValidationError("asset is not a battery")
        soc = connector.read(asset_id, Metric.STATE_OF_CHARGE_PCT)
        capacity = connector.read(asset_id, Metric.CAPACITY_WH)
        memory.add_reading(site_id, soc)
        memory.add_reading(site_id, capacity)
        return {"state_of_charge": soc, "capacity": capacity}

    def estimate_runtime(*, site_id: str, battery_id: str, load_w: float,
                         reserve_pct: float = 20.0) -> dict:
        battery = get_battery_state(site_id=site_id, asset_id=battery_id)
        out = estimate_battery_runtime(battery["capacity"].value,
                                       battery["state_of_charge"].value,
                                       load_w, reserve_pct=reserve_pct)
        return {"hours": out.hours, "usable_energy_wh": out.usable_energy_wh,
                "assumptions": list(out.assumptions), "quality": "estimated"}

    def estimate_cost(*, site_id: str, energy_wh: float, price_per_kwh: float,
                      currency: str = "NGN") -> dict:
        connectors.site(site_id)
        tariff = Tariff(price_per_kwh, currency)
        return {"cost": estimate_energy_cost(energy_wh, tariff), "currency": currency,
                "quality": "estimated"}

    def get_preferences(*, site_id: str) -> dict:
        connectors.site(site_id)
        return memory.preferences(site_id)

    funcs = [
        ("discover_assets", Permission.READ, "List devices in an authorized energy site", discover_assets),
        ("get_asset_state", Permission.READ, "Read an asset's current metric", get_asset_state),
        ("get_energy_history", Permission.READ, "Read a time-bounded metric history", get_energy_history),
        ("get_battery_state", Permission.READ, "Read battery charge and rated capacity", get_battery_state),
        ("estimate_battery_runtime", Permission.ANALYZE, "Approximate battery duration for fixed load", estimate_runtime),
        ("estimate_energy_cost", Permission.ANALYZE, "Estimate tariff cost from Wh and price/kWh", estimate_cost),
        ("get_preferences", Permission.READ, "Read authorized site's user preferences", get_preferences),
    ]
    for name, permission, description, handler in funcs:
        tools.register(ToolSpec(name, description, permission, handler))
