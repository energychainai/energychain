# Upgrading to v0.4.0

## Install and check the version

```bash
python -m pip install --upgrade energychain
python -c "import energychain; print(energychain.__version__)"
python -m pip check
```

To make an application environment reproducible, pin `energychain==0.4.0`.
Model and parser dependencies remain optional:

```bash
python -m pip install 'energychain[models]==0.4.0'
python -m pip install 'energychain[documents]==0.4.0'
python -m pip install 'energychain[all]==0.4.0'
```

## From v0.3.0

Model Gateway, Document Intelligence and the existing tools remain available.
EnergyIntelligence is an additional read/analysis runtime; existing agents and
workflows are not automatically converted into intelligence plans. Start with
[the runtime guide](intelligence-runtime.md), construct an explicit
`IntelligencePlan`, and pass a trusted principal and site to `run()`.

`EnergyIntelligence` is exported by `energychain`. Its typed plans, references,
evidence contracts, SQLite store and event adapter are imported from
`energychain.intelligence_runtime`. No default model provider or background
scheduler is enabled by upgrading.

## From v0.1.0 or v0.2.0

v0.3.0 introduced optional model-provider adapters and document ingestion.
Earlier releases do not have the `models`, `documents` or `all` extras.
v0.2.0 expanded action/approval validation and rejects legacy approval patterns
by default. Review custom approval integrations and keep physical dispatch
disabled while validating the change. The release-specific guides remain
available through the [version selector](versions.md).

## Replay, events and failures

Create a `SQLiteIntelligenceStore` explicitly for persistent run replay and
event-triggered intelligence tasks. An event subscription requires an `on_error`
callback. Completed replay checks current authorization and configured reading
freshness. Reusing a run ID for different task inputs or scope raises
`RunConflict`; an incomplete reserved run requires operator reconciliation.

`EnergyWorkflow` still uses literal step arguments. Use `InputRef` and
`OutputRef` inside an intelligence plan when one tool depends on another result.
`EnergyEventBus` remains synchronous, bounded and process-local. Applications
must provide durable queues, retry handling and monitoring when those are needed.

## Validate your application

Run your own site-permission, provider-contract and data-freshness checks. The
repository examples use simulated data and do not establish field readiness.
From a source checkout, the offline intelligence examples are:

```bash
python examples/intelligence_workflow.py
python examples/intelligence_developer_snapshot.py
python examples/intelligence_incident_event.py
```

The v0.4.0 release passed its five-job Python/OS CI matrix, isolated wheel
installation and official PyPI installation checks. Its published files and
signatures were checked against the tested release artifacts. These results
are engineering evidence for this SDK release, rather than certification of
physical measurements, external providers or hosted production operations.


## Unreleased source-only EnSmith integration relocation (10 Nov 2026)

The `EnSmithTracer`, `EnSmithSpan` and `SPAN_SCHEMA_VERSION` symbols introduced in the **GitHub main branch after the published v0.4.0 release** were experimental and have been moved into the private `energychainai/ensmith` repository, in its optional `ensmith_instrumentation` package.

- **Published PyPI `energychain==0.4.0` is unchanged.**
- Source checkout users of `from energychain import EnSmithTracer` should install the private EnSmith integration using authorized repository access and change imports to `from ensmith_instrumentation import EnSmithTracer`.
- Existing public `EnergyChain(tracer=...)`, `InMemoryTracer` and `TraceEvent` remain supported for local tracing. EnSmith integration stays opt-in; no hosted service or LLM is required.
- The prior public source commit and its MIT permission remain in GitHub history; removing new EnSmith-specific source from main does **not** revoke previously granted rights or make historical code proprietary.
- No package release/version bump or automatic PyPI upload is triggered by this documentation change.

