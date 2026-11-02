"""Reference-app contract against the actual EnergyChain SDK."""
from energychain import EnergyChain
from energychain.intelligence_runtime import (
    EvidenceRule, InputRef, IntelligencePlan, OutputRef, ToolStep,
)


def test_five_step_reference_application_plan_with_real_tools():
    sdk = EnergyChain.demo()
    principal = sdk.principal("reference-test", allowed_sites={"demo-site"})
    plan = IntelligencePlan("energy.backup-review", 1, (
        ToolStep("load", "get_asset_state",
                 {"asset_id": "demo-load", "metric": "power_w"}),
        ToolStep("solar", "get_asset_state",
                 {"asset_id": "demo-solar", "metric": "power_w"}),
        ToolStep("battery", "get_battery_state",
                 {"asset_id": "demo-battery"}),
        ToolStep("runtime", "estimate_battery_runtime", {
            "battery_id": "demo-battery",
            "load_w": OutputRef("load", ("value",)),
            "reserve_pct": InputRef("reserve_pct"),
        }, depends_on=("battery",)),
        ToolStep("balance", "calculate_energy_balance", {
            "solar_w": OutputRef("solar", ("value",)),
            "load_w": OutputRef("load", ("value",)),
            "generator_w": 0.0,
        }),
    ), (
        EvidenceRule("low_soc", "Battery charge below 30%",
                     OutputRef("battery", ("state_of_charge", "value")), "lt", 30),
        EvidenceRule("short_backup", "Backup below two hours",
                     OutputRef("runtime", ("hours",)), "lt", 2),
        EvidenceRule("power_deficit", "Power deficit over 500 W",
                     OutputRef("balance", ("deficit_w",)), "gt", 500),
    ))
    result = sdk.intelligence().run(
        task="Review backup availability", site_id="demo-site",
        principal=principal, plan=plan, inputs={"reserve_pct": 20},
    )
    assert result.status == "completed"
    assert len(result.steps) == 5
    assert len(result.evidence) == 5
    assert len(result.findings) == 3
    assert all(step.status == "succeeded" for step in result.steps)
    assert set(result.evidence[3].parent_evidence_ids) == {
        result.evidence[0].id, result.evidence[2].id
    }
    assert len(result.evidence[2].observed_sources) == 2
    assert result.interpretation_status == "not_requested"
