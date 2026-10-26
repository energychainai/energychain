"""Composable declarative energy skills, with explicit required capabilities."""
from __future__ import annotations
from dataclasses import dataclass
from energychain.exceptions import ValidationError
from energychain.security import Permission
from energychain.tools import ToolRegistry


@dataclass(frozen=True)
class EnergySkill:
    id: str
    description: str
    instructions: str
    tools: tuple[str, ...]
    risk: str = "analysis"

    def __post_init__(self) -> None:
        if (not self.id or not self.description or not self.instructions or
                not self.tools or self.risk not in {"read", "analysis", "prepare"}):
            raise ValidationError("invalid energy skill definition")
        if len(set(self.tools)) != len(self.tools):
            raise ValidationError("duplicate skill tool")


class EnergySkillRegistry:
    def __init__(self, tools: ToolRegistry):
        self.tools = tools
        self._skills: dict[str, EnergySkill] = {}

    def register(self, skill: EnergySkill) -> None:
        if skill.id in self._skills:
            raise ValidationError("duplicate skill")
        specs = {spec["name"]: spec for spec in self.tools.describe()}
        for name in skill.tools:
            if name not in specs or specs[name]["permission"] == Permission.EXECUTE.value:
                raise ValidationError("skill refers to missing or physical execution tool")
        self._skills[skill.id] = skill

    def get(self, name: str) -> EnergySkill:
        return self._skills[name]

    def list(self) -> tuple[EnergySkill, ...]:
        return tuple(self._skills.values())


def install_standard_skills(registry: EnergySkillRegistry) -> None:
    examples = (
        EnergySkill("battery_backup_planning", "Estimate backup availability",
                    "Use only recent measured readings; show reserve and efficiency assumptions; never dispatch.",
                    ("get_battery_state", "estimate_battery_runtime")),
        EnergySkill("energy_cost_insights", "Understand energy expenditure",
                    "State tariff and units; distinguish actual bills from estimated energy cost.",
                    ("estimate_energy_cost", "get_preferences")),
        EnergySkill("fleet_health_review", "Review a multi-site asset fleet",
                    "Check site authorization and missing/stale data; never treat an incomplete fleet as healthy.",
                    ("discover_assets", "get_asset_state")),
    )
    for skill in examples:
        registry.register(skill)
