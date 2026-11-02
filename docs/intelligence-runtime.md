# EnergyIntelligence: evidence-backed SDK workflows

The `energychain.intelligence_runtime` module is a read/analysis-only developer infrastructure layer. It adds **real task execution**, dependency binding, evidence records, optional AI planning, workflow-tool registration, and a bounded in-process event adapter. It is **not** a hosted dashboard or physical equipment controller.

## The public API

```python
from energychain import EnergyChain
from energychain.intelligence_runtime import (
    IntelligencePlan, ToolStep, InputRef, OutputRef, EvidenceRule, format_console
)

sdk = EnergyChain.demo()  # synthetic sources only
principal = sdk.principal("demo-developer", allowed_sites={"demo-site"})

plan = IntelligencePlan("backup-review", 1, (
    ToolStep("load", "get_asset_state",
             {"asset_id": "demo-load", "metric": "power_w"}),
    ToolStep("estimate", "estimate_battery_runtime", {
        "battery_id": "demo-battery",
        "load_w": OutputRef("load", ("value",)),
        "reserve_pct": InputRef("reserve_pct"),
    }),
), rules=(EvidenceRule("short", "Runtime below 2 hours",
    OutputRef("estimate", ("hours",)), "lt", 2),))

report = sdk.intelligence().run(
    task="Review backup availability",
    plan=plan,
    inputs={"reserve_pct": 20},
    principal=principal,
    site_id="demo-site"
)
print(format_console(report))
```

`ToolStep(..., depends_on=(\"battery\",))` can declare required upstream\nprovenance even when a registered tool independently reads an asset. It ensures the\nupstream check succeeded and records its evidence ID; it does not assert that a\nlater tool reused the exact same physical sample.\n\n`OutputRef` refers to the actual prior SDK tool result, **not** a model-invented measurement. Every tool invocation is routed through the existing `ToolRegistry` and site-scoped `SafetyPolicy`.

## Model-planned tasks

**There is no default LLM provider.** The `sdk.intelligence()` runtime works entirely
offline unless a developer explicitly injects a model. No provider is hosted by EnergyChain;
no provider-specific API key is required by the SDK.

Inject a model implementing `TextModel.generate(system, user, context)`. EnergyChain validates its JSON plan against an explicit read/analysis tool allowlist, strictly rejects actions and future references, then executes the approved SDK tools.

```python
import os
from energychain import ModelGateway

model = ModelGateway(
    "openai-compatible", "openai/gpt-oss-20b",
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)
engine = sdk.intelligence(model=model)
result = engine.run(
    task="Check the demo load",
    site_id="demo-site",
    principal=principal,
    inputs={"asset_id": "demo-load"},
    allowed_tools={"get_asset_state"},
    synthesize=True,
)
```

The snippet explicitly selects Groq only as an example of an OpenAI-compatible provider. Developers can instead supply any `TextModel` adapter, including OpenAI, Anthropic, Gemini, Hugging Face, Ollama or a custom implementation. Groq is optional. Deterministic workflows require no model. AI-generated interpretation is labeled `generated_unverified`, and never alters numerical findings.

## Developer snapshot

Run `python examples/intelligence_developer_snapshot.py` from the source checkout
to see three real workflows using synthetic sensor data: manual task submission,
nested execution through `EnergyWorkflow`, and a trusted event trigger. Each uses
the same `EnergyIntelligence` implementation. This example never requires an LLM
or network credentials.

## Existing workflow integration

```python
from energychain import EnergyWorkflow, WorkflowStep

engine = sdk.intelligence().register_tool()
workflow = EnergyWorkflow(sdk.tools, [
    WorkflowStep("energy_intelligence", {
        "task": "Review battery",
        "plan": plan,
        "inputs": {"reserve_pct": 20},
    }),
])
output = workflow.run(principal, "demo-site")
```

The existing `EnergyWorkflow` supports literal step arguments; **cross-step references inside the intelligence plan** are provided by `OutputRef`. There is no claim that the legacy workflow runner now has general-purpose step binding.

## In-process event adapter

```python
from energychain.intelligence_runtime import (
    SQLiteIntelligenceStore, IntelligenceEventRule,
    IntelligenceEventSubscription
)

store = SQLiteIntelligenceStore("intelligence-runs.sqlite3")
engine = sdk.intelligence(store=store)
subscription = IntelligenceEventSubscription(
    bus=sdk.events, engine=engine, principal=principal,
    rule=IntelligenceEventRule(
        category="battery.low", task="Investigate battery",
        plan=plan,
        input_factory=lambda event: {"reserve_pct": 20},
    ),
    on_result=lambda result: print(result.status),
    on_error=lambda error: print(type(error).__name__),
)
# ... subscribe while the process is running ...
subscription.close()
store.close()
```

The service principal comes from a **trusted host**, never the event payload. The current EnergyEventBus is best-effort, synchronous and in-process: for a managed service, use an authenticated durable queue, retries, dead-letter handling and operational alerts.

## Evidence and outputs

`IntelligenceResult` exposes `run_id`, `status`, `outputs`, `steps`, `evidence`, `findings`, and `interpretation_status`. Evidence entries contain actual serialized tool outputs, SHA-256 fingerprints, reading source/quality/timestamps, and `parent_evidence_ids` linking dependent computations. A `VerifiedFinding` is **only** a deterministic numerical comparison against the recorded output, not a verified diagnosis.

`format_console(result)`, `to_json(result)`, and `as_dict(result)` provide presentation adapters. The SDK does not dictate frontend technology.

## Safety and operational boundaries

- Only registered READ/ANALYZE tools; PREPARE and EXECUTE are excluded.
- Caller-supplied `Principal` and trusted `site_id` must authorize before any model planning.
- Input/output references are validated paths; Python `eval`, arbitrary scripts, and recursive agent loops are absent.
- Tool failures are recorded as errors, and downstream steps become `blocked`.
- An optional freshness limit rejects stale/future observed readings.
- A SQLite run ledger supports completed-run replay; incomplete reservations fail closed, requiring operator reconciliation.
- Recognized secret-bearing keys in evidence are redacted, but developers must not send credentials in task inputs or prompts.
- SHA-256 links demonstrate local data consistency; they do **not** certify hardware provenance, physical truth, or tamper-resistant external audit storage.
- Hosted production requires external authentication/tenancy, encryption and retention, data governance, durable queueing, full operational telemetry and verified real-world integrations.

## Test and release gates

Run `python -m pytest -q tests/test_intelligence_runtime_integration.py` plus the entire existing repository test suite. Check the end-to-end CLI example and a real Groq account separately before announcing model-provider compatibility or publishing a new package version. This feature is not automatically a certified physical control or high-availability cloud runtime.
