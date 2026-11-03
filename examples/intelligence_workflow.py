"""Use existing EnergyChain read/analysis tools with bound dependent outputs."""
from energychain import EnergyChain
from energychain.intelligence_runtime import (
    IntelligencePlan, ToolStep, EvidenceRule, InputRef, OutputRef, format_console
)

sdk = EnergyChain.demo()
user = sdk.principal("local-developer", allowed_sites={"demo-site"})

plan = IntelligencePlan(
    "battery-backup-review", 1,
    (
        ToolStep("load", "get_asset_state",
                 {"asset_id": "demo-load", "metric": "power_w"}),
        ToolStep("runtime", "estimate_battery_runtime",
                 {"battery_id": "demo-battery",
                  "load_w": OutputRef("load", ("value",)),
                  "reserve_pct": InputRef("reserve_pct")}),
    ),
    (EvidenceRule("review", "Estimated backup below 2h",
                  OutputRef("runtime", ("hours",)), "lt", 2),),
)

report = sdk.intelligence().run(
    task="Review backup availability",
    principal=user,
    site_id="demo-site",
    inputs={"reserve_pct": 20},
    plan=plan,
)
print(format_console(report))
for e in report.evidence:
    print("EVIDENCE", e.id, e.output_sha256, "parents=", e.parent_evidence_ids)
    for source in e.observed_sources:
        print("SOURCE", source)
