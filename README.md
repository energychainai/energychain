# EnergyChain

**EnergyChain is the developer infrastructure through which AI applications can understand, interact with, and safely optimize energy systems—from solar installations and batteries to mini-grids, utilities, and electricity networks.**

> Status: **v0.3.0 alpha**. Offline-first, Python-first, and read-only by default. Simulated energy data are **not live device measurements**.

EnergyChain brings composable, vendor-neutral energy data types, connectors, safe callable tools, storage, deterministic energy calculations, a pluggable agent interface, and in-process workflows to Python developers. EnergyChain is a **separate project** from Energy Data Network (EDN).

## Installation

Install the current release from the official PyPI index:

```bash
python -m pip install --upgrade energychain
```

To pin the current 0.3.0 alpha SDK:

```bash
python -m pip install energychain==0.3.0
```

For development, install the repository checkout locally:

```bash
python -m pip install -e .
```

Requires Python 3.10 or newer. The core package uses **only Python standard-library runtime dependencies**.

## Model Gateway and Document Intelligence (v0.3)

EnergyChain now offers explicit provider adapters for OpenAI, Anthropic, Gemini,
Hugging Face Inference Providers, local Ollama, and HTTPS OpenAI-compatible endpoints.
The developer supplies credentials and selects an available model; no inference
is hosted. JSON Schema results are validated locally with the models extra.

A tenant-bound Document Intelligence index accepts PDF, DOCX, TXT, Markdown, CSV
and XLSX files, retaining source fingerprints, page/sheet/section provenance,
and explicit energy quantities. The SQLite search index enforces site permissions
and supports optional developer-supplied embeddings.

~~~bash
python -m pip install 'energychain[models]==0.3.0'
python -m pip install 'energychain[documents]==0.3.0'
python -m pip install 'energychain[all]==0.3.0'
~~~

See [Model Gateway](docs/model-gateway.md) and
[Document Intelligence](docs/document-intelligence.md) for APIs, examples and
production security obligations. Offline mock tests do not certify every live
vendor model. Parse untrusted files in an isolated, resource-constrained worker;
document instructions never grant energy device control permissions.

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

## Real-world integrations and safety

New opt-in provider integrations include a **read-only Home Assistant REST connector** (mapped energy sensors, explicit units and bearer authentication) and an **Open-Meteo irradiance forecast source**. Both require legal use of the provider service and a trustworthy source configuration. No vendor integration has yet been field-validated by EnergyChain.

The framework provides site-scoped **fleets**, structured **episodic memory**, a **bounded read/analysis-only planning agent**, constrained **advisory energy scheduling**, signed one-time action approvals, and opt-in **checkpointed read-only workflows**. Physical device dispatch is **disabled by default**. These extensions are libraries and reference implementations, not a production-operated cloud backend.

- [Full 15-module architecture and readiness gates](docs/product-architecture-v01.md)
- [Threat model and authorization boundaries](docs/security.md)
- [Read a Home Assistant energy sensor](examples/home_assistant_readonly.py)
- [Fleet and episodic memory demo](examples/energy_fleet_and_memory.py)

## Expanded components in 0.2

| Component | Implementation |
|---|---|
| Energy models | Site, asset, metric, reading, event, tariff, energy plan |
| Connectors | Abstract connector, registry, simulator, CSV import, read-only Home Assistant; opt-in weather forecast |
| Memory | In-process bounded memory, SQLite persistence, episodic records and context retrieval |
| Energy tools | 18 registered tools covering readings, consumption, forecast baselines, anomaly flags, constraints, fleet snapshots, PV and energy balance |
| Safety | Site authorization, declared action boundaries, one-time signed approvals, execution disabled by default |
| Intelligence | Battery-runtime estimate, tariff cost, baseline mean forecast, outlier baseline |
| Agent | Explicit tool selection, optional injected model, bounded read/analysis planning interface |
| Workflow | In-process sequential tools and SQLite checkpointed read/analysis runs |
| Observability | Bounded trace and latency; model-independent forecast metrics and chronological baseline backtest |
| Developer experience | PyPI-ready packaging, examples, tests, CI and trusted-publisher release workflow |

## Intentionally not included in 0.2

- Field-tested and authenticated integrations with specific solar/battery vendors (no verified live credentials, calibration or deployment yet)
- A production-ready control or dispatch runtime, remote device command implementation, or energy safety certification
- Unbounded/autonomous LLM tool loops, multi-agent coordination, durable multi-instance streaming and production-safe physical action retries
- Production-grade multi-tenant identity, authorization server, encryption/key management, or high-volume telemetry infrastructure
- Trained and field-validated forecasting models, high-confidence anomaly accuracy, hardware testing or independently measured energy savings
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

## Open source and contributing

EnergyChain is an MIT-licensed open-source project. Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, code review and contribution guidelines; [AUTHORS.md](AUTHORS.md) for attribution; [GOVERNANCE.md](GOVERNANCE.md) for project decision-making; and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community expectations.

Use [GitHub issues](https://github.com/energychainai/energychain/issues) for **non-sensitive** bug reports and feature requests. See [SUPPORT.md](SUPPORT.md) for help and [SECURITY.md](SECURITY.md) for private vulnerability reporting. Never include real utility/customer data, meter credentials, or operational endpoints in public reports.

**Before switching a private repository to public**, the maintainer must complete the [open-source launch checklist](docs/open-source-launch-checklist.md), including a full history and credential review. Publishing on PyPI already exposes release source archives; repository visibility is independent.

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

EnergyChain is MIT licensed; see [LICENSE](LICENSE). PyPI wheels and source archives are publicly downloadable independently of GitHub repository visibility. This alpha-quality SDK is not certified for physical energy-equipment control.


## Operational deployment boundary

The package supports **read-only integrations and advisory application development**; it does **not** ship an authenticated multi-tenant backend, durable broker, high-availability workflow workers or certified device controls. A developer can deploy an application that imports it, but responsibility for tenancy, secrets, privacy, monitoring and operational availability belongs to that application until EnergyChain Cloud exists. See `docs/security.md` for release gates.
