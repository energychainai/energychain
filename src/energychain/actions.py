"""Command planning and dry-run service. Physical dispatch is DISABLED by default.

A production dispatch adapter also requires: server-side identity/auth, shared replay ledger,
field-validated equipment constraints, transport trust, equipment acknowledgments and independent
post-command state verification. This package never implies a device command has succeeded.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4
from threading import RLock
from types import MappingProxyType
from energychain.connectors import ConnectorRegistry
from energychain.exceptions import PermissionDenied, UnsupportedCapability, ValidationError
from energychain.models import Capability, EnergyActionSpec, utcnow
from energychain.security import Permission, Principal, SafetyPolicy


@dataclass(frozen=True)
class PreparedAction:
    id: str
    site_id: str
    asset_id: str
    command: str
    parameters: dict[str, float]
    expires_at: datetime
    dry_run: bool = True


@dataclass(frozen=True)
class ActionOutcome:
    action_id: str
    status: str
    provider_response: dict[str, Any] | None = None
    confirmed: bool = False


class ActionService:
    def __init__(self, connectors: ConnectorRegistry, *,
                 policy: SafetyPolicy | None = None, enable_physical_dispatch: bool = False,
                 independent_verifier: Callable[[PreparedAction], bool] | None = None) -> None:
        self.connectors = connectors
        self.policy = policy or SafetyPolicy()
        self.enable_physical_dispatch = enable_physical_dispatch
        self.independent_verifier = independent_verifier
        self._declarations: dict[tuple[str, str], EnergyActionSpec] = {}
        self._prepared: dict[str, PreparedAction] = {}
        self._used: set[str] = set()
        self._lock = RLock()

    def declare(self, declaration: EnergyActionSpec) -> None:
        _, asset = self.connectors.route(declaration.asset_id)
        if Capability.EXECUTE not in asset.capabilities:
            raise UnsupportedCapability("asset connector does not declare physical execution")
        key = declaration.asset_id, declaration.command
        if key in self._declarations:
            raise ValidationError("duplicate action declaration")
        self._declarations[key] = declaration

    def prepare(self, principal: Principal, site_id: str, asset_id: str, command: str,
                parameters: dict[str, float], *, ttl_seconds: int = 120) -> PreparedAction:
        self.policy.authorize(principal, site_id, Permission.PREPARE)
        if not 1 <= ttl_seconds <= 900:
            raise ValidationError("invalid prepared action TTL")
        _, asset = self.connectors.route(asset_id)
        if asset.site_id != site_id:
            raise PermissionDenied("action asset is outside authorized site")
        try:
            declaration = self._declarations[(asset_id, command)]
        except KeyError as exc:
            raise UnsupportedCapability("action is not declared by provider") from exc
        declaration.validate(parameters)
        plan = PreparedAction(str(uuid4()), site_id, asset_id, command,
                              MappingProxyType(dict(parameters)), utcnow()+timedelta(seconds=ttl_seconds))
        self._prepared[plan.id] = plan
        return plan

    def dispatch(self, plan_id: str, principal: Principal, *, approval: str | None = None) -> ActionOutcome:
        # No public execution tools are registered automatically.
        if not self.enable_physical_dispatch:
            raise UnsupportedCapability("physical command execution disabled in SDK")
        try:
            plan = self._prepared[plan_id]
        except KeyError as exc:
            raise ValidationError("unknown prepared action") from exc
        if plan.id in self._used or plan.expires_at < utcnow():
            raise ValidationError("prepared action expired or already attempted")
        _, asset = self.connectors.route(plan.asset_id)
        if asset.site_id != plan.site_id:
            raise PermissionDenied("action asset is outside authorized site")
        # Bind user approval to specific immutable planned parameters and plan ID.
        self.policy.authorize(principal, plan.site_id, Permission.EXECUTE,
                              action=f"dispatch:{plan.command}:{plan.id}",
                              parameters={"asset": plan.asset_id, **plan.parameters}, approval=approval)
        with self._lock:
            if plan.id in self._used:
                raise ValidationError("prepared action already attempted")
            self._used.add(plan.id)  # Consume BEFORE provider I/O; no unsafe retry.
        connector, _ = self.connectors.route(plan.asset_id)
        response = connector.execute(plan.asset_id, plan.command, dict(plan.parameters))
        confirmed = bool(self.independent_verifier(plan)) if self.independent_verifier else False
        return ActionOutcome(plan.id, "verified" if confirmed else "unverified", response,
                             confirmed=confirmed)
