# EnergyChain v0.2.0 — expanded alpha SDK

This release builds on the MIT-licensed v0.1.0 Python SDK without replacing its
published wheel or tag. EnergyChain remains a developer-first framework for
building energy-aware applications, not a utility SCADA or certified controller.

## Added

- Typed energy site/asset topology, constraints, relationships and freshness checks.
- Read-only Home Assistant sensor mapping and opt-in Open-Meteo irradiance forecasts,
  subject to provider permissions, terms and data-quality checks.
- Fleet-scoped snapshots with authorization across every member site and explicit
  missing or stale readings.
- Episodic energy memory, contextual retrieval, source-aware telemetry ingestion,
  event deduplication and a process-local event bus.
- Bounded read/analysis planning agents, declarative skills, expanded energy tools,
  deterministic advisory scheduling, PV estimation and energy-balance calculations.
- Prepared actions with single-use signed approval checks; **physical dispatch is
  disabled by default**.
- SQLite read/analysis workflow checkpoints, forecast evaluation and trace metrics.

## Important compatibility and safety notes

- Expanded action/approval validation rejects the legacy approval pattern by default.
  Check custom integrations before upgrading and keep energy controls read-only
  until an independently verified operator-controlled execution boundary exists.
- No production tenant identity service, field-certified device controls, durable
  hosted agent runtime or independently benchmarked live forecasting model is
  provided.
- Data from the simulator are synthetic. Live provider integrations have not yet
  undergone field validation.
- This version does not include native LLM provider SDK adapters, a PDF/DOCX
  document-ingestion pipeline, RAG, or EnergyChain Cloud.

## Installation

```bash
python -m pip install --upgrade energychain
```

Python 3.10+ is supported. The project remains MIT licensed; wheels and source
distributions are public even though the GitHub development repository is private.
