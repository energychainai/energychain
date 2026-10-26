"""Fleet-scoped read-only aggregation. Explicit partial failures and data freshness."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from energychain.connectors import ConnectorRegistry
from energychain.exceptions import ValidationError
from energychain.models import EnergyReading, Metric, ensure_aware, require_fresh, utcnow
from energychain.security import Principal, Permission, SafetyPolicy


@dataclass(frozen=True)
class Fleet:
    id: str
    site_ids: frozenset[str]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.site_ids or any(not s for s in self.site_ids):
            raise ValidationError("fleet id and nonempty site set required")
        object.__setattr__(self, "site_ids", frozenset(self.site_ids))


@dataclass(frozen=True)
class FleetFailure:
    site_id: str
    asset_id: str
    reason: str


@dataclass(frozen=True)
class FleetSnapshot:
    fleet_id: str
    timestamp: datetime
    metric: Metric
    observations: tuple[EnergyReading, ...]
    failures: tuple[FleetFailure, ...]
    # Sum is deliberately omitted: power on a generator, PV and a load cannot be
    # naively added to produce a meaningful net site power.


class FleetManager:
    def __init__(self, connectors: ConnectorRegistry, policy: SafetyPolicy | None = None) -> None:
        self.connectors = connectors
        self.policy = policy or SafetyPolicy()
        self._fleets: dict[str, Fleet] = {}

    def register(self, fleet: Fleet) -> None:
        if fleet.id in self._fleets:
            raise ValidationError("fleet id already registered")
        for site_id in fleet.site_ids:
            self.connectors.site(site_id)
        self._fleets[fleet.id] = fleet

    def site_ids(self, fleet_id: str) -> frozenset[str]:
        return self._fleets[fleet_id].site_ids

    def snapshot(self, fleet_id: str, principal: Principal, metric: Metric, *,
                 max_age_seconds: float = 300, now: datetime | None = None) -> FleetSnapshot:
        fleet = self._fleets[fleet_id]
        # Fail the entire request rather than return data for an implicitly narrower fleet.
        for site_id in fleet.site_ids:
            self.policy.authorize(principal, site_id, Permission.READ)
        point = now or utcnow()
        ensure_aware(point)
        data: list[EnergyReading] = []
        failures: list[FleetFailure] = []
        for site_id in sorted(fleet.site_ids):
            for asset in self.connectors.assets(site_id):
                connector, _ = self.connectors.route(asset.id)
                try:
                    r = connector.read(asset.id, Metric(metric))
                    require_fresh(r, maximum_age_seconds=max_age_seconds, now=point)
                    data.append(r)
                except (LookupError, ValidationError, RuntimeError) as exc:
                    failures.append(FleetFailure(site_id, asset.id, type(exc).__name__))
                except Exception as exc:
                    # Do not leak provider credentials or network error strings in fleet output.
                    failures.append(FleetFailure(site_id, asset.id, type(exc).__name__))
        return FleetSnapshot(fleet_id, point, Metric(metric), tuple(data), tuple(failures))
