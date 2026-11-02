# EnergyChain v0.4.0 — EnergyIntelligence SDK

## New developer-facing capability

- `EnergyChain.intelligence()`: a provider-neutral, explicit READ/ANALYZE task engine.
- `IntelligencePlan`, `ToolStep`, `InputRef`, and `OutputRef`: typed manual task and output dependency contracts.
- Evidence records: actual SDK tool outputs, structured readings, source quality, fingerprints, and dependency links.
- `EvidenceRule`: deterministic checks of numeric tool outputs.
- Existing `EnergyWorkflow` integration through `register_tool()`.
- Event integration through `IntelligenceEventSubscription` and `EnergyEventBus`.
- Optional model-planned workflows via injected `TextModel` and explicit tool allowlists.
- SQLite ledger for bounded local run replay, machine-readable JSON and CLI formatters.
- No selected or default model provider; optional Groq or other vendor configuration is supplied by the developer.

## Runtime release fixes

- Completed-run replay rechecks current tool permissions and blocked actions before returning stored outputs, and binds the request to the principal's site scope.
- Model-planned retries replay the persisted selected steps and result using the original request identity, without requiring another provider call.
- Datetime task inputs and dependent tool values retain their types during invocation; evidence remains serialized and recognized secret fields stay redacted.
- Freshness limits validate every returned reading, including readings beyond the 200-source provenance summary and cached results at replay time.
- SQLite replay and JSON adapters preserve structural step IDs while continuing to redact credential fields inside tool payloads.

## Developer examples

```bash
python examples/intelligence_workflow.py
python examples/intelligence_incident_event.py
```

The event example detects a synthetic battery condition with a real SDK sensor tool, emits an event, executes a seven-step investigation, and displays its evidence record.

## Important limitations

This is an in-process, read/analysis-only SDK feature, not a multi-tenant hosted service, reliable distributed event broker, physical controller, or validated field-deployed energy decision platform. Its deterministic rules produce verifiable comparisons, not independently certified equipment diagnoses. Applications must provide trusted authentication, operational monitoring, data-source validation, secrets storage and appropriate safeguards.

## Release safeguards

Before publishing a new release, verify official PyPI project ownership, the existing trusted publisher identity for the moved GitHub organization, GitHub environment approvals, CI results, package metadata, exact release provenance, and an unpinned installation from official PyPI. The release workflow is set to stop on failed gates. No model credentials should be packaged.
