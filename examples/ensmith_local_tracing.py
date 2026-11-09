"""Capture genuine SDK tool execution metadata for a future EnSmith collector."""

import json

from energychain import EnergyChain, EnSmithTracer
from energychain.connectors import HybridSiteSimulator

tracer = EnSmithTracer(max_events=100)
chain = EnergyChain(tracer=tracer)
chain.add_connector("demo", HybridSiteSimulator())

# This convenience principal is for a local SDK demo, not a hosted identity.
principal = chain.principal("local-developer", allowed_sites={"demo-site"})
assets = chain.tools.invoke("discover_assets", principal, "demo-site")
assert assets, "expected simulated demonstration assets"

print(json.dumps(tracer.span_dicts(), indent=2))
