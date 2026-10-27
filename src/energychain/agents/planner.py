"""Bounded observation-only tool-planning agent, not an autonomous device controller."""
from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Any
from energychain.agents.model import TextModel
from energychain.exceptions import ToolError, ValidationError
from energychain.security import Permission, Principal
from energychain.tools import ToolRegistry


@dataclass(frozen=True)
class ToolChoice:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class BoundedAgentResult:
    answer: str
    tool_calls: tuple[ToolChoice, ...]
    tool_results: tuple[Any, ...]


class BoundedEnergyAgent:
    """Model selects a bounded read/analytics plan; caller's tool registry enforces policies.

    Structured planner output: {"steps":[{"name":"...","arguments":{...}}], "answer":"..."}.
    The model never receives approval tokens, secrets, or a physical EXECUTE capability.
    There are no recursive calls, loops of self-planning, or implicit control actions.
    """
    def __init__(self, tools: ToolRegistry, model: TextModel, *, max_calls: int = 4,
                 allowed_tools: set[str] | None = None) -> None:
        if not 1 <= max_calls <= 12:
            raise ValidationError("max_calls must be 1..12")
        self.tools = tools
        self.model = model
        self.max_calls = max_calls
        self.allowed_tools = frozenset(allowed_tools) if allowed_tools else None

    def run(self, question: str, *, principal: Principal, site_id: str) -> BoundedAgentResult:
        if not question or len(question) > 4096:
            raise ValidationError("invalid agent question length")
        desc = [t for t in self.tools.describe() if t["permission"] in
                {Permission.READ.value, Permission.ANALYZE.value} and
                (self.allowed_tools is None or t["name"] in self.allowed_tools)]
        names = {t["name"] for t in desc}
        system = ("Energy analyst. Respond ONLY with JSON object keys steps and answer. "
                  "steps must be an array of at most " + str(self.max_calls) +
                  " read/analysis tool calls {name,arguments}. Never propose physical commands. "
                  "Tool descriptions: " + json.dumps(desc, sort_keys=True))
        raw = self.model.generate(system, question, "No readings supplied; request only necessary tools.")
        if not isinstance(raw, str) or len(raw) > 16_384:
            raise ValidationError("planner output too large or not text")
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict) or set(obj) != {"steps", "answer"}:
                raise ValueError("planner JSON keys must be steps, answer")
            steps = obj["steps"]
            if not isinstance(steps, list) or len(steps) > self.max_calls:
                raise ValueError("too many planned tool calls")
            choices = []
            for step in steps:
                if (not isinstance(step, dict) or set(step) != {"name", "arguments"} or
                    step["name"] not in names or not isinstance(step["arguments"], dict)):
                    raise ValueError("unauthorized tool selection")
                # Validate JSON values now, not after tool invocation.
                json.dumps(step["arguments"], allow_nan=False)
                choices.append(ToolChoice(step["name"], step["arguments"]))
            if not isinstance(obj["answer"], str) or len(obj["answer"]) > 4096:
                raise ValueError("answer must be bounded text")
        except (ValueError, TypeError, KeyError) as exc:
            raise ToolError("model produced invalid or unsafe structured tool plan") from exc
        outcomes = []
        for choice in choices:
            outcomes.append(self.tools.invoke(choice.name, principal, site_id,
                                              arguments=choice.arguments))
        # Model output is intent/preliminary wording; never manufacture evidence from result.
        return BoundedAgentResult(obj["answer"], tuple(choices), tuple(outcomes))
