"""Sequential, permission-gated, fail-closed workflow prototype."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from energychain.security import Principal
from energychain.tools import ToolRegistry


@dataclass(frozen=True)
class WorkflowStep:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowResult:
    succeeded: bool
    outputs: tuple[Any, ...]
    failed_step: int | None = None
    error: str | None = None


class EnergyWorkflow:
    """In-process sequential workflow; no durable jobs or scheduled actions in v0.1."""
    def __init__(self, tools: ToolRegistry, steps: list[WorkflowStep]) -> None:
        self.tools = tools
        self.steps = tuple(steps)

    def run(self, principal: Principal, site_id: str) -> WorkflowResult:
        outputs: list[Any] = []
        for i, step in enumerate(self.steps):
            try:
                outputs.append(self.tools.invoke(step.tool_name, principal, site_id,
                                                 arguments=step.arguments))
            except Exception as exc:
                return WorkflowResult(False, tuple(outputs), i, str(exc))
        return WorkflowResult(True, tuple(outputs))
