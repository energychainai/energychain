# EnSmith opt-in local instrumentation (experimental)

**Requirements:** INC-SMITH-001A / SMITH-F-001 / NFR-OBS-001. **Status:** reviewed through GitHub pull request; **not the hosted EnSmith product**.

`EnSmithTracer` is a dependency-free, experimental extension of the existing SDK's `InMemoryTracer`. It converts **real tool-registry events** to a bounded local list of versioned span metadata without uploading anything. It does not require EnGraph, a paid account, API key, LLM, or EnergyChain Cloud.

## Try it

```python
from energychain import EnergyChain, EnSmithTracer
from energychain.connectors import HybridSiteSimulator

tracer = EnSmithTracer(max_events=100)
chain = EnergyChain(tracer=tracer)
chain.add_connector("demo", HybridSiteSimulator())
principal = chain.principal("developer", allowed_sites={"demo-site"})

chain.tools.invoke("discover_assets", principal, "demo-site")
for span in tracer.span_dicts():
    print(span)
```

Run `python examples/ensmith_local_tracing.py` in a configured SDK checkout. It executes a real tool using **simulated input data** and prints genuine tool-event metadata.

For optional ModelGateway metadata, pass `on_trace=tracer.record_model_trace` to a developer-selected `ModelGateway`. Model providers and credentials remain explicit; no model is required for tool tracing.

## Data policy

- **Metadata-only by construction:** exported spans contain no raw tool arguments/results, prompt/response text, documents, site IDs, principal IDs, or `TraceEvent.detail` strings.
- Span IDs are randomly generated. Raw correlation IDs remain process-local, grouped within a bounded cache, and do not appear in exported spans. Operation/model names are constrained to safe identifier syntax.
- `EnSmithTracer` is **opt-in**. Span and original SDK event buffers are bounded by `max_events`. Note that `events()` still exposes the SDK's usual **local** identity/detail fields; only `span_dicts()` exposes the sanitized schema.
- No outbound requests or automatic tracing uploads occur.
- Nonproduction hosted collection, authentication, tenancy, encryption, retention/deletion, service export, and Studio trace exploration are **not implemented here**.

## Compatibility and limitations

`EnergyChain(tracer=EnSmithTracer())` uses the existing injection hook; the base `InMemoryTracer` remains unchanged. The experimental `ensmith.span.v0` schema may change during hosted protocol review. Hierarchical EnGraph state traces and general OpenTelemetry interchange are separate increments.

The captured timestamps are UTC; invalid source timestamps get a distinct instrumentation timestamp rather than being interpreted as UTC. Correlation groups are local to one tracer instance and can be evicted when the buffer reaches capacity. Trace metadata is not automatically durable.
