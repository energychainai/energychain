"""High-level framework composition entrypoint."""
from __future__ import annotations
from energychain.agents import EnergyAgent, TextModel
from energychain.connectors import ConnectorRegistry, EnergyConnector, HybridSiteSimulator
from energychain.memory import EnergyMemory, InMemoryEnergyMemory
from energychain.observability import InMemoryTracer
from energychain.security import Principal, SafetyPolicy
from energychain.tools import ToolRegistry, install_builtin_tools
from energychain.tools.extended import install_extended_tools
from energychain.memory import InMemoryEpisodeStore, EnergyContextBuilder, EpisodeStore
from energychain.fleets import FleetManager
from energychain.skills import EnergySkillRegistry, install_standard_skills
from energychain.actions import ActionService
from energychain.telemetry import TelemetryIngestor, EnergyEventBus
from energychain.agents import BoundedEnergyAgent


class EnergyChain:
    """Compose connectors, site-isolated memory, safe tools and optional LLMs."""
    def __init__(self, *, memory: EnergyMemory | None = None,
                 policy: SafetyPolicy | None = None,
                 tracer: InMemoryTracer | None = None,
                 episodes: EpisodeStore | None = None) -> None:
        self.connectors = ConnectorRegistry()
        self.memory = memory if memory is not None else InMemoryEnergyMemory()
        self.tracer = tracer if tracer is not None else InMemoryTracer()
        self.tools = ToolRegistry(policy=policy, tracer=self.tracer)
        install_builtin_tools(self.tools, self.connectors, self.memory)
        self.episodes = episodes if episodes is not None else InMemoryEpisodeStore()
        self.context = EnergyContextBuilder(self.memory, self.episodes)
        self.fleets = FleetManager(self.connectors, policy=self.tools.policy)
        self.telemetry = TelemetryIngestor(self.connectors, self.memory)
        self.events = EnergyEventBus()
        self.actions = ActionService(self.connectors, policy=self.tools.policy)
        install_extended_tools(self.tools, self.connectors, self.memory,
                               self.fleets, self.context)
        self.skills = EnergySkillRegistry(self.tools)
        install_standard_skills(self.skills)

    @classmethod
    def demo(cls) -> "EnergyChain":
        chain = cls()
        chain.add_connector("demo", HybridSiteSimulator())
        return chain

    def add_connector(self, name: str, connector: EnergyConnector) -> None:
        self.connectors.register(name, connector)

    def agent(self, model: TextModel | None = None) -> EnergyAgent:
        return EnergyAgent(self.tools, model=model)

    def principal(self, identity: str, *, allowed_sites: set[str]) -> Principal:
        """Local demo convenience only. Never use this to self-issue production credentials."""
        return Principal(identity, frozenset(allowed_sites))

    def planning_agent(self, model: TextModel, *, max_calls: int = 4,
                       allowed_tools: set[str] | None = None) -> BoundedEnergyAgent:
        """Model may select read/analysis tools only; no physical execution tools."""
        return BoundedEnergyAgent(self.tools, model, max_calls=max_calls,
                                  allowed_tools=allowed_tools)
