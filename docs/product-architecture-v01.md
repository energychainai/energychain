# EnergyChain v0.4.0 — Technical Architecture and Release Boundary

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
       |-- ModelGateway -> explicit provider adapters / structured outputs / metadata traces
       |-- EnergyKnowledgeBase -> bounded document parsing / tenant-site retrieval / citations
       |-- EnergyIntelligence -> typed dependent task plan / deterministic evidence rules
       |    |-- SQLiteIntelligenceStore -> authorized completed-run replay
       |    +-- IntelligenceEventSubscription -> trusted in-process event adapter
       |-- EnergySkillRegistry -> declarative instructions and tool bundles
       |-- Scheduling -> exact bounded, deterministic, advisory-only optimization
       |-- TelemetryIngestor -> source ID deduplication / freshness / site validation
       |-- EnergyEventBus -> process-local subscribers (not broker)
       |-- SQLiteWorkflowCheckpoints -> read/analysis jobs, restart idempotency
       +-- ActionService -> bounded preparation, disabled physical dispatch
```

## Master inventory of 15 system modules

| Module | v0.4.0 SDK capabilities | Not delivered in this SDK |
|---|---|---|
| 1. Energy Core | Typed sites/assets/readings/units, topology relations, numerical constraints, source quality | Certified equipment ontology or protocol conformance |
| 2. Connectors | Registry, CSV, deterministic simulator, read-only HA mapping, opt-in weather | Verified specific solar/battery vendors / proprietary hardware protocols |
| 3. Energy Context | Scoped history, preferences, episodes and tenant/site document passages with citations | Managed retrieval lifecycle, hosted vector infrastructure or certified source truth |
| 4. Energy Tools | 18 registered reading/analysis/planning tools; reserved argument protection | Arbitrary third-party action execution |
| 5. Energy Memory | In-memory/SQLite readings, events, notes, preferences and episodic stores | Encrypted tenant database, retention policy enforcement, distributed scale |
| 6. Model Integration | `TextModel` injection; six explicit Model Gateway adapter families; optional JSON validation | Managed inference, supplied provider credentials or guaranteed live-account interoperability |
| 7. Agents | Explicit tool agent, bounded planner and provider-neutral EnergyIntelligence task engine | Self-directed multi-agent autonomy, physical command agents |
| 8. Safety | Permission levels, site checks, bounded planned actions, signed one-time approvals | Independent human approval service, field safety certification |
| 9. Workflows | Sequential flow, local checkpoints, typed dependent intelligence steps, completed-run replay | Distributed scheduler, high-availability workers, exactly-once physical actions |
| 10. Energy Intelligence | Runtime/cost/PV/balance tools, baselines, bounded planning, tool-output evidence and deterministic findings | Validated ML/forecasting models, certified diagnoses or hardware-validated dispatch optimization |
| 11. Skills & Prompts | Reusable battery, cost, fleet skill contracts | Agent marketplace, production instruction hierarchy |
| 12. Events & Streaming | Bounded local event bus, validated telemetry ingestion, trusted intelligence subscription adapter | MQTT/Kafka broker, backpressure, multi-instance durable subscriptions |
| 13. Evaluation & Observability | Site-scoped trace, latency, forecast MAE/RMSE/bias/MAPE, chronological holdout | Operational SLOs / tracing backend integration / accuracy benchmarks |
| 14. Developer SDK | Pure-Python package, typing, samples, CI workflows and packaging | TypeScript SDK, hosted playground, stable v1 API guarantees |
| 15. EnergyChain Cloud | **Not included** | Managed tenants, connectors, billing, RBAC, secrets, quotas and audit data plane |

## Contracts and invariants

### Models, documents and intelligence tasks

Model Gateway and Document Intelligence were introduced in v0.3.0.
EnergyIntelligence was introduced in v0.4.0. They are optional application
components: no provider is selected, no credentials are supplied and no inference
is hosted by default. Documents retain source fingerprints and citations under
tenant/site checks; production hosts must isolate untrusted parsing and govern
storage. Intelligence plans bind actual SDK outputs through typed references,
apply deterministic rules and record dependent evidence. An interpretation from
a model remains unverified and cannot authorize a tool or certify a measurement.

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
Local SQLite checkpoints reduce accidental reruns of READ/ANALYZE operations and reject changing an existing run ID's scope/plan. The intelligence ledger also rechecks current permissions and configured freshness when replaying a completed task. An incomplete reservation requires operator reconciliation. The event adapter uses a host-owned principal, a run store and an error callback. These components do not provide distributed execution, automatic abandoned-run recovery or exactly-once device commands. Scheduling, operational retries and a transactional outbox remain external infrastructure responsibilities.

### Developer experience and release
Normal app installation does not require any paid API provider. `EnergyChain.demo()` is explicitly synthetic. The MIT-licensed SDK is published on PyPI and maintained in the public `energychainai/energychain` repository. Releases require the configured Trusted Publisher, passing release gates and independently verified installation. Any externally accessible hosted service built on this library needs its own security and operational validation.

## Minimum field-readiness acceptance gates

Field-readiness and provider/hardware gates below have not been established by
the SDK release. The packaging gate is separately verified for v0.4.0; it does
not establish the other gates.

1. A named, consented, supported real energy provider integration on a live installation with operator permission.
2. Hardware/vendor-specific units and measurement semantics validated against manufacturer documentation and calibrated or verified ground truth.
3. Site and organization RBAC managed by a trusted external identity provider and isolated persistent stores.
4. Provenance, freshness, drift, missing-data and duplicate checks run continuously on live telemetry.
5. Rate limits, egress allowlists, retries, circuit breaking, credential rotation, comprehensive encrypted storage and security tests.
6. Workflow replay, concurrency, failure injection, restart and outage tests with declared RTO/RPO.
7. Action-specific hazard analysis, human sign-off, equipment interlocks and independent command outcome verification before any physical dispatch.
8. Real historical backtests for forecasting quality, including out-of-distribution and seasonal holdouts.
9. Licensing and privacy policy approved for actual data sources and users.
10. PyPI Trusted Publishing configured, CI green across supported Python versions, and clean installation verified from official PyPI. **Verified for v0.4.0**; see [release evidence](releasing.md).

## Roadmap decision

The expanded SDK should be useful *without* connected hardware but not misrepresented as field-approved energy operations. Focus near-term validation on a real user's read-only data source + reliable context/memory + a reproducible developer reference use case; introduce controlled execution only after its independent trust boundary exists.
