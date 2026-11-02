"""Real EnergyChain SDK integration: no synthetic replacement tool registry."""
import pytest

from energychain import EnergyChain, EnergyWorkflow, WorkflowStep
from energychain.exceptions import PermissionDenied
from energychain.intelligence_runtime import (
    IntelligencePlan, ToolStep, InputRef, OutputRef, EvidenceRule,
    format_console, to_json,
)


def test_existing_sdk_tools_feed_actual_outputs_into_downstream_steps():
    sdk=EnergyChain.demo()
    user=sdk.principal("sdk-integration", allowed_sites={"demo-site"})
    plan=IntelligencePlan("backup",1,(
        ToolStep("load","get_asset_state",{"asset_id":"demo-load","metric":"power_w"}),
        ToolStep("runtime","estimate_battery_runtime",{
            "battery_id":"demo-battery",
            "load_w":OutputRef("load",("value",)),
            "reserve_pct":InputRef("reserve_pct"),
        }),
    ),(EvidenceRule("short","Estimated runtime below two hours",
                    OutputRef("runtime",("hours",)),"lt",2.0),))
    result=sdk.intelligence().run(task="Review backup",site_id="demo-site",
                                   principal=user,inputs={"reserve_pct":20},plan=plan)
    assert result.status=="completed"
    assert result.outputs["runtime"]["hours"]>=0
    assert result.outputs["load"]["value"]>0
    assert result.evidence[0].observed_sources[0].quality=="simulated"
    assert result.evidence[0].observed_sources[0].source=="hybrid-simulator"
    assert result.evidence[1].parent_evidence_ids==(result.evidence[0].id,)
    assert len(result.plan_sha256)==64
    assert "get_asset_state" in format_console(result)
    assert '"evidence"' in to_json(result)


def test_engine_is_callable_from_existing_energyworkflow():
    sdk=EnergyChain.demo()
    principal=sdk.principal("sdk-integration",allowed_sites={"demo-site"})
    sdk.intelligence().register_tool()
    plan=IntelligencePlan("battery",1,(
        ToolStep("read","get_battery_state",{"asset_id":"demo-battery"}),
    ))
    workflow=EnergyWorkflow(sdk.tools,[
        WorkflowStep("energy_intelligence",{"task":"Review battery","inputs":{},"plan":plan})
    ])
    response=workflow.run(principal,"demo-site")
    assert response.succeeded
    assert response.outputs[0].status=="completed"
    assert len(response.outputs[0].evidence)==1


def test_site_scope_denies_before_tool_execution():
    sdk=EnergyChain.demo()
    user=sdk.principal("restricted",allowed_sites={"different-site"})
    plan=IntelligencePlan("read",1,(
        ToolStep("reading","get_asset_state",{"asset_id":"demo-load","metric":"power_w"}),
    ))
    with pytest.raises(PermissionDenied):
        sdk.intelligence().run(task="Cross-site read",site_id="demo-site",principal=user,plan=plan)


def test_ai_planner_cannot_select_execute_capability():
    from energychain.intelligence_runtime import PlanRejected
    class Model:
        def generate(self,*args):
            return '{"id":"ai-task","version":1,"steps":[{"id":"bad","tool":"execute_energy_action","arguments":{}}]}'
    sdk=EnergyChain.demo()
    user=sdk.principal("test",allowed_sites={"demo-site"})
    with pytest.raises(PlanRejected):
        sdk.intelligence(model=Model()).run(task="Dispatch",site_id="demo-site",principal=user,
                                            allowed_tools={"get_asset_state"})


def test_generated_interpretation_is_not_verified_evidence():
    sdk=EnergyChain.demo()
    user=sdk.principal("test",allowed_sites={"demo-site"})
    class Model:
        def generate(self,system,user_prompt,context):
            assert "evidence_ids" in context
            return "Suggested review only."
    plan=IntelligencePlan("read",1,(
        ToolStep("load","get_asset_state",{"asset_id":"demo-load","metric":"power_w"}),
    ))
    report=sdk.intelligence(model=Model()).run(task="Check load",site_id="demo-site",
                                                principal=user,plan=plan,synthesize=True)
    assert report.status=="completed"
    assert report.interpretation_status=="generated_unverified"
