# EnergyChain

**EnergyChain is the developer infrastructure through which AI applications can understand, interact with, and safely optimize energy systems—from solar installations and batteries to mini-grids, utilities, and electricity networks.**

> Status: **v0.1.0 alpha**. Offline-first, Python-first, and read-only by default. Simulated energy data are **not live device measurements**.

EnergyChain brings composable, vendor-neutral energy data types, connectors, safe callable tools, storage, deterministic energy calculations, a pluggable agent interface, and in-process workflows to Python developers. EnergyChain is a **separate project** from Energy Data Network (EDN).

## Installation

```bash
python -m pip install energychain
```

To pin this release:

```bash
python -m pip install energychain==0.1.0
```

Requires Python 3.10 or newer. The core package uses **only Python standard-library runtime dependencies**.

## Quickstart

```python
from energychain import EnergyChain

chain = EnergyChain.demo()
user = chain.principal("developer", allowed_sites={"demo-site"})

assets = chain.tools.invoke("discover_assets", user, "demo-site")
print([a.name for a in assets])

result = chain.tools.invoke(
    "estimate_battery_runtime", user, "demo-site",
    arguments={"battery_id": "demo-battery", "load_w": 900, "reserve_pct": 20},
)
print(result)
```

**Security:** `principal()` is a **local-demo convenience**, not a production authentication mechanism. Production applications must authenticate principals, assign site-level permissions from a trusted service, and enforce authorization at API boundaries. The included connector simulator never sends live control commands.

## Components available in 0.1

| Component | Implementation |
|---|---|
| Energy models | Site, asset, metric, reading, event, tariff, energy plan |
| Connectors | Abstract connector, registry, deterministic hybrid site simulator, CSV import |
| Memory | In-process bounded memory, SQLite durable persistence |
| Energy tools | Asset discovery, state, history, battery state, runtime and cost estimates, preferences |
| Safety | Permission scope, site boundaries and optional action-specific execution approval |
| Intelligence | Battery-runtime estimate, tariff cost, baseline mean forecast, outlier baseline |
| Agent | Explicit tool selection plus optional injected text-model callback |
| Workflow | In-process fail-closed sequential tool execution |
| Observability | In-memory bounded trace events |
| Developer experience | PyPI-ready packaging, examples, tests, CI and trusted-publisher release workflow |

## Intentionally not included in 0.1

- Authenticated integrations with third-party solar/battery vendors (no verified API credentials or access yet)
- A production-ready control or dispatch runtime, remote device command implementation, or energy safety certification
- Autonomous LLM tool selection, multi-agent coordination, event subscriptions, distributed scheduling or durable workflow retries
- Production-grade multi-tenant identity, authorization server, encryption/key management, or high-volume telemetry infrastructure
- Trained forecasting models, validated anomaly detection accuracy, hardware testing or independently measured energy savings
- Managed EnergyChain Cloud, hosted APIs, TypeScript SDK, vector-search services or MCP adapter

These are subsequent product-development efforts, not features to advertise as shipped.

## Connect existing CSV exports

Provide `asset_id,metric,value,timestamp,source` columns and register an explicit `EnergySite` and its `EnergyAsset` definitions. See `CSVConnector.from_csv(path, site=..., assets=...)`. The latest row is treated as the last *recorded* value (not necessarily live); caller must check freshness before operational decisions.

## Design principles

1. **Developer-first:** EnergyChain is software infrastructure for developers, not a national-grid control product.
2. **Standard energy semantics:** W, Wh, %, UTC-offset-aware timestamps, data-source and quality fields.
3. **Composable:** Connectors, tools, memory and language models can be independently replaced.
4. **Data is not authority:** An LLM response cannot issue a physical command. Tools always check policies.
5. **Provenance matters:** Simulated, estimated and measured values are explicitly labelled.
6. **Tests and evidence:** Do not confuse synthetic demonstrations with field validation.

## Local development

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m build
python -m twine check dist/*
python examples/quickstart.py
```

See [architecture](docs/architecture.md) for contract boundaries and limitations and [release guide](docs/releasing.md) for verified distribution steps.

## Licensing and safety

EnergyChain is distributed under the [MIT License](LICENSE). Published wheels and source archives are publicly downloadable even though the development repository is private. Alpha-quality software: not warranted for physically controlling energy equipment.
