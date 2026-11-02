"""Run a real offline developer snapshot of EnergyIntelligence.

From the EnergyChain repository checkout:
    python examples/intelligence_developer_snapshot.py

Shows manual tasks, SDK workflow registration, and a simulated event trigger.
No remote LLM, network, cloud, or real energy equipment required.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from energychain import EnergyChain, EnergyEvent, EnergyWorkflow, WorkflowStep
from energychain.intelligence_runtime import (
    EvidenceRule, InputRef, IntelligenceEventRule,
    IntelligenceEventSubscription, IntelligencePlan, OutputRef,
    SQLiteIntelligenceStore, ToolStep, format_console,
)


def main():
    sdk = EnergyChain.demo()
    principal = sdk.principal("snapshot-developer", allowed_sites={"demo-site"})
    plan = IntelligencePlan("backup-review", 1, (
        ToolStep("load", "get_asset_state",
                 {"asset_id": "demo-load", "metric": "power_w"}),
        ToolStep("estimate", "estimate_battery_runtime", {
            "battery_id": "demo-battery",
            "load_w": OutputRef("load", ("value",)),
            "reserve_pct": InputRef("reserve"),
        }),
    ), (
        EvidenceRule("short-runtime", "Estimated backup below 2 hours",
                     OutputRef("estimate", ("hours",)), "lt", 2.0),
    ))

    with TemporaryDirectory() as tmp:
        store = SQLiteIntelligenceStore(Path(tmp) / "runs.sqlite")
        runtime = sdk.intelligence(store=store)
        manual = runtime.run(task="Assess backup", site_id="demo-site",
                             principal=principal, plan=plan,
                             inputs={"reserve": 20}, run_id="manual-demo")
        print("=== MANUAL SDK TASK ===")
        print(format_console(manual))

        runtime.register_tool()
        workflow = EnergyWorkflow(sdk.tools, [
            WorkflowStep("energy_intelligence", {
                "task": "Assess backup as a workflow step",
                "plan": plan,
                "inputs": {"reserve": 25},
            }),
        ])
        nested = workflow.run(principal, "demo-site")
        print("\n=== ENERGYCHAIN WORKFLOW COMPOSITION ===")
        print(format_console(nested.outputs[0]))

        outcomes = []
        errors = []
        subscription = IntelligenceEventSubscription(
            bus=sdk.events, engine=runtime, principal=principal,
            rule=IntelligenceEventRule(
                "battery.low", "Investigate triggered backup event", plan,
                input_factory=lambda event: {"reserve": 30},
            ),
            on_result=outcomes.append,
            on_error=errors.append,
        )
        sdk.events.publish(EnergyEvent(
            "local-event-01", "demo-site", "battery.low",
            "Sample event; no physical equipment involved"))
        subscription.close()
        print("\n=== TRUSTED EVENT ADAPTER ===")
        if errors:
            raise RuntimeError(f"Event adapter failed: {type(errors[0]).__name__}")
        print(format_console(outcomes[0]))
        store.close()


if __name__ == "__main__":
    main()
