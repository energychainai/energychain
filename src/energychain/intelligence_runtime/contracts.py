"""Typed, framework-independent contracts for evidence-backed intelligence tasks.

All outputs are data, not operational authorizations. Read/analysis only.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


@dataclass(frozen=True)
class InputRef:
    """Use a validated task input; never interpolate strings or evaluate expressions."""
    name: str


@dataclass(frozen=True)
class OutputRef:
    """Access a successful earlier tool output by explicit path."""
    step_id: str
    path: tuple[str | int, ...] = ()


@dataclass(frozen=True)
class ToolStep:
    id: str
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceRule:
    """Deterministic numerical comparison; not an LLM-derived finding."""
    id: str
    label: str
    value: OutputRef
    op: Literal["lt", "le", "gt", "ge", "eq", "ne"]
    threshold: float
    severity: Literal["info", "attention", "critical"] = "attention"


@dataclass(frozen=True)
class IntelligencePlan:
    id: str
    version: int
    steps: tuple[ToolStep, ...]
    rules: tuple[EvidenceRule, ...] = ()


@dataclass(frozen=True)
class SourceEvidence:
    asset_id: str
    metric: str
    value: float
    unit: str
    source: str
    quality: str
    observed_at: str


@dataclass(frozen=True)
class StepRecord:
    id: str
    tool: str
    status: Literal["succeeded", "failed", "blocked"]
    evidence_id: str | None
    duration_ms: float
    arguments: dict[str, Any]
    error_code: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    step_id: str
    tool: str
    inputs_sha256: str
    output_sha256: str
    observed_sources: tuple[SourceEvidence, ...]
    result: Any
    created_at: str
    parent_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedFinding:
    id: str
    label: str
    severity: str
    satisfied: bool
    actual: float
    operator: str
    threshold: float
    evidence_id: str


@dataclass(frozen=True)
class IntelligenceResult:
    run_id: str
    task: str
    status: Literal["completed", "failed", "partial"]
    plan_id: str
    plan_version: int
    site_id: str
    outputs: dict[str, Any]
    steps: tuple[StepRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    findings: tuple[VerifiedFinding, ...]
    interpretation: str | None = None
    interpretation_status: str = "not_requested"
    error_code: str | None = None
    created_at: str = ""
    plan_sha256: str = ""
    inputs_sha256: str = ""


class IntelligenceError(RuntimeError):
    """Expected error without leaking backend exception contents."""


class PlanRejected(IntelligenceError):
    pass


class RunConflict(IntelligenceError):
    pass


class EvidenceError(IntelligenceError):
    pass
