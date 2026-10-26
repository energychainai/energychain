"""Permission-scoped tool authorization independent of AI model outputs."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from energychain.exceptions import ApprovalRequired, PermissionDenied


class Permission(str, Enum):
    READ = "read"
    ANALYZE = "analyze"
    PREPARE = "prepare"
    EXECUTE = "execute"


@dataclass(frozen=True)
class Principal:
    id: str
    allowed_sites: frozenset[str]
    permissions: frozenset[Permission] = frozenset({Permission.READ, Permission.ANALYZE})

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_sites", frozenset(self.allowed_sites))
        object.__setattr__(self, "permissions", frozenset(Permission(p) for p in self.permissions))
        if not self.id:
            raise ValueError("principal id cannot be empty")


@dataclass(frozen=True)
class Approval:
    """External, non-LLM approval artifact, issued to a scoped action."""
    principal_id: str
    site_id: str
    action: str
    approved: bool


@dataclass
class SafetyPolicy:
    """Rejects missing site access, missing permission and unapproved physical execution."""
    require_execution_approval: bool = True
    blocked_actions: frozenset[str] = field(default_factory=frozenset)

    def authorize(self, principal: Principal, site_id: str, permission: Permission,
                  *, action: str = "", approval: Approval | None = None) -> None:
        if site_id not in principal.allowed_sites:
            raise PermissionDenied(f"principal has no access to site {site_id}")
        if permission not in principal.permissions:
            raise PermissionDenied(f"missing permission: {permission.value}")
        if action and action in self.blocked_actions:
            raise PermissionDenied(f"action blocked by policy: {action}")
        if permission == Permission.EXECUTE and self.require_execution_approval:
            if (approval is None or not approval.approved or approval.principal_id != principal.id
                    or approval.site_id != site_id or approval.action != action):
                raise ApprovalRequired("action-specific, external approval required")
