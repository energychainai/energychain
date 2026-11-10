# EnergyChain

**Developer infrastructure for energy AI.**

EnergyChain is an energy AI infrastructure company building the software foundation for applications that understand, analyze, and help optimize distributed energy systems — including solar, batteries, hybrid power, and mini-grids.

**This repository contains the open-source EnergyChain SDK**, the foundation developers can use to build energy-aware applications with reusable energy data models, connectors, permission-scoped tools, context, model integrations and evidence-backed workflows. Build useful intelligence without rebuilding the same energy-specific infrastructure for every application.

[Company website](https://energychain.app/) · [Documentation](https://energychain.app/docs/) · [PyPI package](https://pypi.org/project/energychain/) · [Examples](examples/) · [Issues](https://github.com/energychainai/energychain/issues)

## What developers can build

- **Energy asset intelligence:** connect and normalize readings, analyze conditions, and produce evidence-backed findings.
- **Battery and hybrid-power applications:** estimate runtime, calculate tariffs, review PV and energy balance, and investigate events.
- **Energy-aware AI agents:** give developer-selected models permission-scoped energy tools with explicit authorization boundaries.
- **Repeatable intelligence workflows:** compose dependent tool steps, reference real outputs, evaluate deterministic evidence rules and replay results.
- **Document-powered energy applications:** work with source-linked PDF, spreadsheet and report context.
- **Multi-site intelligence:** build on scoped memories, fleet models, local events and reusable analysis patterns.

The SDK supplies building blocks; developers retain control of their application's frontend, data sources, model providers and deployment.

## Install and run

Requires Python 3.10+.

```bash
python -m pip install --upgrade energychain
```

The current documented SDK release is **v0.4.0 alpha**:

```bash
python -m pip install energychain==0.4.0
```

```python
from energychain import EnergyChain

chain = EnergyChain.demo()
developer = chain.principal("developer", allowed_sites={"demo-site"})

assets = chain.tools.invoke("discover_assets", developer, "demo-site")
print([asset.name for asset in assets])

result = chain.tools.invoke(
    "estimate_battery_runtime",
    developer,
    "demo-site",
    arguments={"battery_id": "demo-battery", "load_w": 900, "reserve_pct": 20},
)
print(result)
```

`EnergyChain.demo()` supplies simulated data for getting started. Applications can use explicitly configured authorized sources and connectors when ready.

**Next step:** [Follow the v0.4.0 developer guide](https://energychain.app/docs/0.4.0/) or [run an intelligence workflow](examples/intelligence_workflow.py).

## EnergyChain SDK v0.4.0

| Component | Developer value |
| --- | --- |
| Typed energy models | Consistent site, asset, reading, event, tariff and unit semantics |
| Data connectors | CSV, simulator, read-only Home Assistant mapping and opt-in irradiance forecast |
| Permission-scoped tools | Asset queries, battery runtime, energy costs, PV and energy-balance calculations, baselines |
| Energy memory and context | Scoped observations, event history, episodic context and SQLite persistence |
| Model Gateway | Explicit, developer-selected model adapters, including OpenAI, Anthropic, Gemini, Hugging Face, Ollama and compatible HTTPS endpoints |
| Document Intelligence | Site-scoped, source-linked search for PDF, DOCX, text, Markdown, CSV and XLSX |
| EnergyIntelligence | Real tool-output dependencies, typed plans, deterministic findings, provenance and replay |
| Workflows and events | In-process workflow steps, local checkpoints and trusted event subscriptions |
| Tracing and evaluation | Execution traces, latency and baseline forecast metrics |

### EnergyIntelligence

Introduced in **v0.4.0**, EnergyIntelligence runs evidence-backed analysis through `chain.intelligence().run(...)`. You can also register `energy_intelligence` as a workflow tool or subscribe through `IntelligenceEventSubscription`. Findings are linked to actual SDK tool outputs and source records.

- [EnergyIntelligence runtime guide](docs/intelligence-runtime.md)
- [Model Gateway](docs/model-gateway.md)
- [SDK optional telemetry and generic trace hooks](docs/telemetry-opt-in.md)
- [Document Intelligence](docs/document-intelligence.md)
- [Architecture](docs/architecture.md)
- [Versioned documentation](docs/versions.md)
- [Runnable examples](examples/)

The core SDK works without a model subscription. **There is no default LLM provider.** Applications opt into a model and supply credentials when needed.

```bash
python -m pip install 'energychain[models]==0.4.0'
python -m pip install 'energychain[documents]==0.4.0'
python -m pip install 'energychain[all]==0.4.0'
```

## The EnergyChain product ecosystem

**EnergyChain is the company. EnergyChain SDK is one product.** The SDK is the currently released foundation for the broader infrastructure ecosystem.

| Product | Purpose | Current status |
| --- | --- | --- |
| **EnergyChain SDK** | Open-source energy data, tools and intelligence building blocks | **Available:** v0.4.0 alpha |
| **EnGraph** | Stateful orchestration for more complex energy AI workflows | **Planned product** |
| **EnSmith** | Centralized tracing, evaluation, debugging and monitoring | **Planned product** |
| **EnergyChain Cloud** | Managed execution, infrastructure and operational services | **Planned service** |

The SDK already includes local workflows and tracing; the proposed products would add capabilities beyond those existing primitives.

**Building energy software for an organization?** Visit [energychain.app](https://energychain.app/) to explore a pilot, integration or potential design partnership.

## Why EnergyChain?

1. **Energy-aware data models:** power, energy, source quality, site access and timestamps have explicit meanings.
2. **Reusable integrations:** developers can combine data sources without tying every workflow to a single vendor schema.
3. **Evidence-backed intelligence:** workflows use real tool outputs and traceable source context.
4. **Explicit permissions:** model suggestions do not grant application privileges.
5. **Model-agnostic development:** AI providers are optional and developer-selected.
6. **Composable infrastructure:** adopt only the capabilities a product needs.

Detailed integration responsibilities and operational requirements live in the [technical architecture](docs/product-architecture-v01.md) and [security documentation](docs/security.md).

## Open source

The SDK is [MIT licensed](LICENSE). We welcome issues, contributions and discussions about energy data, applications and integrations.

[Contributing](CONTRIBUTING.md) · [Governance](GOVERNANCE.md) · [Security reporting](SECURITY.md) · [Support](SUPPORT.md) · [Code of conduct](CODE_OF_CONDUCT.md)

EnergyChain is an independent venture, separate from Energy Data Network (EDN). See [Governance](GOVERNANCE.md) for project stewardship.

## Local development

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m build
python -m twine check dist/*
python examples/quickstart.py
```

Learn more about the company at [energychain.app](https://energychain.app/) and develop with the [SDK docs](https://energychain.app/docs/).

## Private EnSmith integration (unreleased source migration)

EnSmith-specific tracing and services are developed in the **private** `energychainai/ensmith` repository. The public EnergyChain SDK keeps generic `InMemoryTracer` and `TraceEvent` hooks; the private optional adapter provides EnSmith-branded `EnSmithTracer`. The experimental EnSmith exports previously present **only in an unreleased GitHub main-source change** were moved before any new PyPI release. The published SDK v0.4.0 was unaffected. Previously public MIT-licensed GitHub history remains public and MIT-licensed; this migration does not undo that history.
