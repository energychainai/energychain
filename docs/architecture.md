# EnergyChain v0.4.0 architecture

## Scope
EnergyChain is an embedded Python SDK for reading, normalizing, remembering,
analyzing and explaining energy observations. It provides simulator/CSV
connectors, opt-in read-only Home Assistant mapping and Open-Meteo irradiance,
permission-scoped tools, local memory, model adapters, document retrieval and
bounded intelligence workflows. It supplies no hosted identity service, managed
inference, distributed scheduler or certified physical control runtime.

## Component dependency direction
`EnergyChain` assembles a `ConnectorRegistry`, memory, `ToolRegistry`, context,
fleets and local events. Agents, `EnergyWorkflow` and `EnergyIntelligence` consume
the same tool registry. Every invocation passes through its site-scoped
`SafetyPolicy`; a model response never creates authority to call a tool.

```text
Trusted host identity and site authorization
  -> EnergyChain client
       -> ConnectorRegistry -> normalized sites, assets and readings
       -> Memory / episodes -> bounded, scoped context
       -> ToolRegistry -> SafetyPolicy -> READ / ANALYZE tools
            -> explicit agent or bounded model planner
            -> sequential EnergyWorkflow / local checkpoints
            -> EnergyIntelligence -> dependent steps -> evidence and findings
                 -> optional SQLite completed-run ledger
                 -> optional trusted EnergyEventBus subscription
       -> optional ModelGateway -> developer-selected external provider
       -> optional EnergyKnowledgeBase -> bounded local document parsing/index
```

## Three orchestration contracts

`EnergyAgent` runs an explicitly selected tool. `BoundedEnergyAgent` accepts a
finite allowlisted read/analysis plan from an injected model. Neither grants
hardware privileges to the model.

`EnergyWorkflow` executes ordered steps with literal arguments. Its SQLite
checkpoints concern local read/analysis replay; they do not make physical actions
exactly-once or turn the host into a distributed worker.

`EnergyIntelligence`, introduced in v0.4.0, adds typed `IntelligencePlan` and
`ToolStep` contracts. `InputRef` binds task inputs and `OutputRef` binds an earlier
successful tool output. Deterministic `EvidenceRule` comparisons consume those
outputs. Dependencies, step errors, blocked steps and evidence links are recorded.
The default limit is eight steps, configurable from one to twelve. A model is
optional and has no default provider. See [the runtime guide](intelligence-runtime.md).

## Models and documents

`ModelGateway` has explicit adapters for OpenAI, Anthropic, Gemini, Hugging Face
Inference Providers, Ollama and HTTPS OpenAI-compatible endpoints. The developer
selects the provider/model and supplies credentials. Structured JSON validation
uses the optional `models` extra; no model inference is hosted by the SDK.

`EnergyKnowledgeBase` parses and indexes local text, Markdown, CSV, PDF, DOCX and
XLSX with tenant/site checks, bounded ingestion and source citations. Keyword
retrieval uses SQLite FTS5; optional embeddings are supplied by the developer.
PDF and Office parsers use the optional `documents` extra. Untrusted document
parsing belongs in an isolated resource-constrained worker. Retrieval citations
do not establish the truth of generated statements.

## Persistence and event delivery

`SQLiteIntelligenceStore` binds completed runs to their request, principal and
site. Replay rechecks current authorization and any configured freshness limit.
Changed requests or scope raise `RunConflict`; an abandoned reservation requires
operator reconciliation. It is not an automatic recovery worker.

`EnergyEventBus` is bounded, synchronous and process-local. The intelligence
adapter requires a store and an error callback; its service principal comes from
the trusted host. Durable transport, operational retries and delivery monitoring
remain responsibilities of the embedding application.

## Domain conventions
- Power (instantaneous) = W; energy (integrated) = Wh. Do not interchange.
- Battery charge is percentage [0,100]; capacity is Wh.
- Datetime objects must contain timezone information.
- Source and data quality (measured, estimated, simulated) are mandatory for readings.
- Assets and sites use stable, provider-independent identifiers; registry disallows duplicate IDs across connectors.

## Trust boundaries
- A caller constructs authenticated `Principal` from external authorization; `EnergyChain.principal()` is for demos only.
- Every tool invocation is site-scoped, and handlers validate an asset's registered site against that scope.
- A tool's permission level is not derived from LLM output.
- An explicit agent, bounded planner or intelligence engine invokes tools only through the registry and current site policy. A model never grants permission.
- Standard connector `execute` fails with `UnsupportedCapability` unless consciously implemented by a third-party adapter.
- Future physical execution must enforce equipment constraints, device authorization, human approval, auditable logs and post-action verification.
- Local SQLite and in-memory stores are not substitutes for production tenant isolation or infrastructure security.
- Tool return data must be treated as untrusted, and the runtime is not a prompt-injection defense for arbitrary LLM implementations.

## Memory semantics
In-memory records are bounded per site; SQLite stores readings, events, notes and JSON-encoded preferences. The caller must ensure every recording matches the actual site identity. A dedicated production memory backend should enforce ownership at the storage layer and add retention/deletion policies.

## Calculations
Battery runtime computes `capacity_wh * max(soc - reserve,0)/100 * efficiency / load_w`. A zero load returns `None` (unbounded in this idealized equation, not infinite guaranteed device runtime). Mean forecast and z-score anomaly detection are transparent baselines, not validated ML predictors. Financial calculation multiplies energy (Wh)/1000 by tariff currency per kWh.

## Production responsibilities

Production applications supply trusted identity, tenant isolation, provider
credentials, storage encryption, retention and operational monitoring.
SDK fingerprints establish local consistency, not hardware authenticity or a
tamper-resistant external audit service. Equipment constraints, human approval,
interlocks and independent post-action verification remain authoritative.

See the [15-module inventory](product-architecture-v01.md),
[threat model](security.md), [migration guide](upgrading.md) and
[release-specific documentation](versions.md).
