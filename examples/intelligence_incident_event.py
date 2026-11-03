"""Real SDK event trigger -> investigation -> evidence; runnable without LLM/cloud.

A host monitor detects a condition using an actual EnergyChain tool. It emits an
EnergyEvent that the registered intelligence subscriber handles using its trusted
principal. The event alone cannot confer permissions. Uses synthetic simulator.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from energychain import EnergyChain, EnergyEvent
from energychain.intelligence_runtime import (
    IntelligencePlan, ToolStep, InputRef, OutputRef, EvidenceRule,
    SQLiteIntelligenceStore, IntelligenceEventRule,
    IntelligenceEventSubscription, format_console,
)


def run():
    sdk = EnergyChain.demo()
    principal = sdk.principal("example-service", allowed_sites={"demo-site"})
    now = datetime.now(timezone.utc)
    plan = IntelligencePlan("energy.event-investigation", 1, (
        ToolStep("load", "get_asset_state",
                 {"asset_id": "demo-load", "metric": "power_w"}),
        ToolStep("solar", "get_asset_state",
                 {"asset_id": "demo-solar", "metric": "power_w"}),
        ToolStep("battery", "get_battery_state", {"asset_id": "demo-battery"}),
        ToolStep("runtime", "estimate_battery_runtime", {
            "battery_id": "demo-battery",
            "load_w": OutputRef("load", ("value",)),
            "reserve_pct": InputRef("reserve_pct"),
        }, depends_on=("battery",)),
        ToolStep("balance", "calculate_energy_balance", {
            "solar_w": OutputRef("solar", ("value",)),
            "load_w": OutputRef("load", ("value",)),
        }),
        ToolStep("history", "get_energy_history", {
            "asset_id": "demo-load", "metric": "power_w",
            "start": now - timedelta(hours=24), "end": now,
        }, depends_on=("load",)),
        ToolStep("anomalies", "detect_anomalies", {
            "asset_id": "demo-load", "metric": "power_w",
            "start": now - timedelta(hours=24), "end": now,
        }, depends_on=("history",)),
    ), (
        EvidenceRule("low_soc", "Battery below 80%", OutputRef(
            "battery", ("state_of_charge", "value")), "lt", 80),
        EvidenceRule("short_backup", "Backup below 2 hours", OutputRef(
            "runtime", ("hours",)), "lt", 2),
        EvidenceRule("deficit", "Power deficit above 500W", OutputRef(
            "balance", ("deficit_w",)), "gt", 500),
        EvidenceRule("load_spike", "Anomalous loads present", OutputRef(
            "anomalies", ("count",)), "gt", 0),
    ))

    with TemporaryDirectory() as tmp, SQLiteIntelligenceStore(
        Path(tmp) / "runs.sqlite3"
    ) as store:
        engine = sdk.intelligence(store=store)  # no default LLM
        reports, errors = [], []
        subscriber = IntelligenceEventSubscription(
            bus=sdk.events, engine=engine, principal=principal,
            rule=IntelligenceEventRule(
                "energy.risk.detected", "Investigate event-backed condition",
                plan, lambda event: {"reserve_pct": 20},
            ),
            on_result=reports.append,
            on_error=errors.append,
        )
        try:
            # The detector reads a real registered SDK tool, not hardcoded values.
            battery = sdk.tools.invoke(
                "get_battery_state", principal, "demo-site",
                arguments={"asset_id": "demo-battery"},
            )
            observed_soc = battery["state_of_charge"].value
            if observed_soc < 80:  # illustrative detector threshold
                sdk.events.publish(EnergyEvent(
                    "risk-" + uuid4().hex, "demo-site", "energy.risk.detected",
                    "Synthetic battery SOC fell below monitoring policy 80%",
                ))
            if errors:
                raise RuntimeError("Event callback failed: " + type(errors[0]).__name__)
            if len(reports) != 1:
                raise RuntimeError("Expected one event-triggered investigation")
            report = reports[0]
            assert report.status == "completed"
            assert len(report.evidence) == 7
            assert all(step.status == "succeeded" for step in report.steps)
            assert len(report.evidence[3].parent_evidence_ids) == 2
            print(format_console(report))
            print("Actual SOC that triggered event:", observed_soc)
            print("PASS: seven real SDK tools, four deterministic findings")
        finally:
            subscriber.close()


if __name__ == "__main__":
    run()
