"""High-level framework composition entrypoint."""
from __future__ import annotations
from energychain.agents import EnergyAgent, TextModel
from energychain.connectors import ConnectorRegistry, EnergyConnector, HybridSiteSimulator
from energychain.memory import EnergyMemory, InMemoryEnergyMemory
from energychain.observability import InMemoryTracer
from energychain.security import Principal, SafetyPolicy
from energychain.tools import ToolRegistry, install_builtin_tools


class EnergyChain:
    """Compose connectors, site-isolated memory, safe tools and optional LLMs."""
    def __init__(self, *, memory: EnergyMemory | None = None,
                 policy: SafetyPolicy | None = None,
                 tracer: InMemoryTracer | None = None) -> None:
        self.connectors = ConnectorRegistry()
        self.memory = memory if memory is not None else InMemoryEnergyMemory()
        self.tracer = tracer if tracer is not None else InMemoryTracer()
        self.tools = ToolRegistry(policy=policy, tracer=self.tracer)
        install_builtin_tools(self.tools, self.connectors, self.memory)

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
