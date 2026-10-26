"""Model-independent callable energy tool interfaces and centralized authorization."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from energychain.exceptions import ToolError
from energychain.observability import InMemoryTracer, TraceEvent
from energychain.security import Approval, Permission, Principal, SafetyPolicy


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    permission: Permission
    handler: Callable[..., Any]
    # For exact site/asset checks, tools supply site_id after server-side resolution.


class ToolRegistry:
    def __init__(self, policy: SafetyPolicy | None = None,
                 tracer: InMemoryTracer | None = None) -> None:
        self.policy = policy or SafetyPolicy()
        self.tracer = tracer or InMemoryTracer()
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or spec.name in self._tools:
            raise ValueError("tool name must be nonempty and unique")
        self._tools[spec.name] = spec

    def describe(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description,
                 "permission": t.permission.value} for t in self._tools.values()]

    def invoke(self, name: str, principal: Principal, site_id: str, *,
               arguments: dict[str, Any] | None = None, approval: Approval | None = None) -> Any:
        try:
            spec = self._tools[name]
        except KeyError as exc:
            raise ToolError(f"unknown tool: {name}") from exc
        # Do not accept unverified, arbitrary site_id as authority: handlers additionally
        # route assets and verify that their owner site equals this authorized site.
        try:
            self.policy.authorize(principal, site_id, spec.permission, action=name, approval=approval)
            result = spec.handler(site_id=site_id, **(arguments or {}))
            self.tracer.record(TraceEvent(name, principal.id, site_id, "success"))
            return result
        except Exception as exc:
            self.tracer.record(TraceEvent(name, principal.id, site_id, "denied_or_failed", detail=type(exc).__name__))
            raise
