# EnergyChain v0.1 architecture contract

## Scope
Python framework for reading, normalizing, remembering, analyzing and explaining basic energy observations. Included connectors are a synthetic hybrid site simulator and a read-only CSV telemetry-import adapter; no branded live vendor API is claimed. No first-party hosted services or direct control integration is included.

## Component dependency direction
`EnergyChain` assembles `ConnectorRegistry`, `EnergyMemory`, `ToolRegistry`, and `EnergyAgent`; workflow is an independent consumer of the tool registry. Energy adapters implement `EnergyConnector`. Authorized actions are checked at `ToolRegistry.invoke`. All default tool handlers are read/analysis only.

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
- The model cannot dynamically invoke tools via `EnergyAgent` v0.1.
- Standard connector `execute` fails with `UnsupportedCapability` unless consciously implemented by a third-party adapter.
- Future physical execution must enforce equipment constraints, device authorization, human approval, auditable logs and post-action verification.
- Local SQLite and in-memory stores are not substitutes for production tenant isolation or infrastructure security.
- Tool return data must be treated as untrusted, and the runtime is not a prompt-injection defense for arbitrary LLM implementations.

## Memory semantics
In-memory records are bounded per site; SQLite stores readings, events, notes and JSON-encoded preferences. The caller must ensure every recording matches the actual site identity. A dedicated production memory backend should enforce ownership at the storage layer and add retention/deletion policies.

## Calculations
Battery runtime computes `capacity_wh * max(soc - reserve,0)/100 * efficiency / load_w`. A zero load returns `None` (unbounded in this idealized equation, not infinite guaranteed device runtime). Mean forecast and z-score anomaly detection are transparent baselines, not validated ML predictors. Financial calculation multiplies energy (Wh)/1000 by tariff currency per kWh.

## Next compatibility points
Connectors: authenticated public vendor APIs; memory: production time-series store; models: external LLM APIs; workflows: checkpoints and idempotency; adapters: MCP/other agent runtimes; future optional hosted offering.
