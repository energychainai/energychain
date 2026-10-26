# EnergyChain v0.1 — Deep Technical Architecture and Release Boundary

## Core positioning

**EnergyChain is the developer infrastructure through which AI applications can understand, interact with, and safely optimize energy systems—from solar installations and batteries to mini-grids, utilities, and electricity networks.**

EnergyChain and Energy Data Network (EDN) are separate ventures. This SDK is built for software/AI developers; it is **not** a SCADA replacement, national-grid controller or proprietary asset management dashboard. A deployable application that imports an SDK is still responsible for its own web API, operational staffing, authentication, observability backends, infrastructure and independent validations.

## Execution model and ownership

```text
Developer-built energy app
  |-- Identity and tenant boundary (host app, not provided by SDK)
  |-- EnergyChain client
       |-- ConnectorRegistry -> normalized EnergySite / EnergyAsset / EnergyReading
       |    |-- Deterministic hybrid simulator
       |    |-- Timezone-aware CSV import
       |    +-- Opt-in read-only Home Assistant API mapper (verified against REST schema)
       |-- Opt-in Open-Meteo weather irradiance source (forecast != power generation)
       |-- ToolRegistry -> scopes/permissions -> domain intelligence -> TraceEvent
       |-- Memory -> in-process / SQLite time-series, events, preferences + episodic memory
       |-- Context builder -> bounded, site-scoped retrieval
       |-- FleetManager -> all-site access checks, missing/stale observations
       |-- EnergyAgent -> explicit, caller-selected read/analysis tool
       |-- BoundedEnergyAgent -> validated finite read/analysis plan from injected model
       |-- EnergySkillRegistry -> declarative instructions and tool bundles
       |-- Scheduling -> exact bounded, deterministic, advisory-only optimization
       |-- TelemetryIngestor -> source ID deduplication / freshness / site validation
       |-- EnergyEventBus -> process-local subscribers (not broker)
       |-- SQLiteWorkflowCheckpoints -> read/analysis jobs, restart idempotency
       +-- ActionService -> bounded preparation, disabled physical dispatch
```

## Master inventory of 15 system modules

| Module | v0.1 delivered capabilities | Not delivered in this SDK |
|---|---|---|
| 1. Energy Core | Typed sites/assets/readings/units, topology relations, numerical constraints, source quality | Certified equipment ontology or protocol conformance |
| 2. Connectors | Registry, CSV, deterministic simulator, read-only HA mapping, opt-in weather | Verified specific solar/battery vendors / proprietary hardware protocols |
| 3. Energy Context | Scoped history, user preferences, structured episode context | Grounded vector RAG with lifecycle management |
| 4. Energy Tools | 18 registered reading/analysis/planning tools; reserved argument protection | Arbitrary third-party action execution |
| 5. Energy Memory | In-memory/SQLite readings, events, notes, preferences and episodic stores | Encrypted tenant database, retention policy enforcement, distributed scale |
| 6. Model Integration | Language model injection via `TextModel` protocol | Direct provider SDK integrations / model serving |
| 7. Agents | Explicit tool agent and bounded planner with allowlisted tools | Self-directed multi-agent autonomy, physical command agents |
| 8. Safety | Permission levels, site checks, bounded planned actions, signed one-time approvals | Independent human approval service, field safety certification |
| 9. Workflows | Sequential flow and SQLite read-only checkpointing | Distributed scheduler, high-availability workers, exactly-once physical actions |
| 10. Energy Intelligence | Runtime, tariffs, PV/balance estimation, mean forecast, z-score anomaly baseline, exact bounded load planner | Validated ML/forecasting models, hardware-validated dispatch optimization |
| 11. Skills & Prompts | Reusable battery, cost, fleet skill contracts | Agent marketplace, production instruction hierarchy |
| 12. Events & Streaming | Bounded local event bus, validated telemetry ingestion | MQTT/Kafka broker, backpressure, multi-instance durable subscriptions |
| 13. Evaluation & Observability | Site-scoped trace, latency, forecast MAE/RMSE/bias/MAPE, chronological holdout | Operational SLOs / tracing backend integration / accuracy benchmarks |
| 14. Developer SDK | Pure-Python package, typing, samples, CI workflows and packaging | TypeScript SDK, hosted playground, stable v1 API guarantees |
| 15. EnergyChain Cloud | **Not included** | Managed tenants, connectors, billing, RBAC, secrets, quotas and audit data plane |

## Contracts and invariants

### Energy Core
All readings are unit-specific and timezone-aware; `W` power is not `Wh` energy. A point-in-time reading has provider `source`, data `quality` and `timestamp`. Calculations make assumptions explicit, reject nonfinite values and avoid pretending that static models certify hardware safety. Topology and load scheduling operate on per-site, registered entities. Fleet aggregations do not sum heterogeneous generators, solar and loads into a meaningless total.

### Connectors and sources
Every connector MUST declare sites/assets and consistently associate readings to asset IDs and units. Connector capabilities describe supported operations, not user authorization. The read-only Home Assistant adapter maps developer-approved entities, requires a Bearer access token and an HTTPS origin, validates incoming entity ID and unit, and never calls mutation endpoints. Data-source integrations are opt-in and require user-provided legal access and API credentials. Open-Meteo returns forecast **shortwave irradiance**, not measured solar PV output; `estimate_pv_power` applies an explicit simple efficiency ratio. **Check Open-Meteo's commercial license/terms before monetized use.**

### Memory
Structured observations belong in time-series/SQL storage; episodes capture evidence-backed historical events and outcomes, and user preferences are explicit structured keys. Semantic/vector retrieval is intentionally **not** used for numeric power or energy calculations. Memory retrieval is bounded and site-scoped. Raw source truth, derived context and model conclusions must be distinguished, with observation freshness considered for decisions. SQLite implementations are **trusted single-process** prototypes, not a hosted multi-tenant store.

### Tools and agent runtime
Tools are deterministic functions returning typed objects, not free-text power measurements invented by a model. Permissions are enforced before each call; high-risk action classes are excluded from the bounded planner entirely. The planner accepts only strict JSON with a pre-declared list of allowed read/analysis tools and at most 12 calls; no recursive tool-agent loops, model-authored credentials, or implicit execution privileges.

### Actions and safety
The model may recommend or request a plan, but a different trust domain must evaluate physical action parameters and consent. The built-in `ActionService` is a **prepare-first, dispatch-off-by-default** extension point; approval tokens use HMAC binding to exact arguments, intended principal/site, expiry and a single-use nonce. The issuer must live outside the end-user application, and industrial use requires independent post-action validation and hardware controls.

### Workflows and agents
Durable SQLite checkpoints reduce accidental reruns of READ/ANALYZE operations and reject changing an existing run ID's scope/plan. This is not a durable executor for device commands; scheduler, credential rotation, operational retries and transactional outbox are future infrastructure. In-process workflow is also retained for small deterministic tool pipelines.

### Developer experience and release
Normal app installation does not require any paid API provider. `EnergyChain.demo()` is explicitly synthetic. PyPI distribution requires separate publisher authorization and legal licensing decision, regardless of private GitHub visibility. Any externally accessible hosted service built on this library needs independent security/deployment review.

## Minimum field-readiness acceptance gates (not yet passed)

1. A named, consented, supported real energy provider integration on a live installation with operator permission.
2. Hardware/vendor-specific units and measurement semantics validated against manufacturer documentation and calibrated or verified ground truth.
3. Site and organization RBAC managed by a trusted external identity provider and isolated persistent stores.
4. Provenance, freshness, drift, missing-data and duplicate checks run continuously on live telemetry.
5. Rate limits, egress allowlists, retries, circuit breaking, credential rotation, comprehensive encrypted storage and security tests.
6. Workflow replay, concurrency, failure injection, restart and outage tests with declared RTO/RPO.
7. Action-specific hazard analysis, human sign-off, equipment interlocks and independent command outcome verification before any physical dispatch.
8. Real historical backtests for forecasting quality, including out-of-distribution and seasonal holdouts.
9. Licensing and privacy policy approved for actual data sources and users.
10. PyPI Trusted Publishing configured, CI green across all supported Python versions, clean installation smoke-tested from official index.

## Roadmap decision

The first release should be useful *without* connected hardware but not misrepresented as field-approved energy operations. Focus near-term validation on a real user's read-only data source + reliable context/memory + a reproducible developer reference use case; introduce controlled execution only after its independent trust boundary exists.
