"""Security, persistence and event acceptance tests using the real SDK."""
import json
import pytest
from energychain import EnergyChain, EnergyEvent
from energychain.security import Permission
from energychain.tools import ToolSpec
from energychain.intelligence_runtime import (
    IntelligencePlan, ToolStep, PlanRejected,
    SQLiteIntelligenceStore, IntelligenceEventRule, IntelligenceEventSubscription,
    RunConflict
)


def example():
    return IntelligencePlan("read-load",1,(
        ToolStep("read","get_asset_state",{"asset_id":"demo-load","metric":"power_w"}),
    ))


def test_idempotent_sqlite_replay_without_calling_provider_twice(tmp_path):
    sdk=EnergyChain.demo()
    user=sdk.principal("operator", allowed_sites={"demo-site"})
    with SQLiteIntelligenceStore(tmp_path/"runs.sqlite") as store:
        engine=sdk.intelligence(store=store)
        p={"task":"Check site","plan":example(),"site_id":"demo-site",
           "principal":user,"run_id":"run-123"}
        initial=engine.run(**p)
        replay=engine.run(**p)
        assert initial.status=="completed"
        assert replay==initial
        with pytest.raises(RunConflict):
            engine.run(**{**p,"task":"Different task"})


def test_incomplete_run_requires_reconciliation(tmp_path):
    with SQLiteIntelligenceStore(tmp_path/"runs.sqlite") as store:
        assert store.reserve("run1","user1","demo-site","sha") is None
        with pytest.raises(RunConflict):
            store.reserve("run1","user1","demo-site","sha")


def test_event_trigger_reuses_trusted_principal_and_deduplicates(tmp_path):
    sdk=EnergyChain.demo()
    principal=sdk.principal("trusted-worker", allowed_sites={"demo-site"})
    results=[]
    errors=[]
    with SQLiteIntelligenceStore(tmp_path/"events.sqlite") as store:
        engine=sdk.intelligence(store=store)
        subscription=IntelligenceEventSubscription(
            bus=sdk.events,engine=engine,principal=principal,
            rule=IntelligenceEventRule("battery.low","Read load",example(),lambda event:{}),
            on_result=results.append,on_error=errors.append)
        event=EnergyEvent("e-101","demo-site","battery.low","test event")
        sdk.events.publish(event)
        sdk.events.publish(event)
        subscription.close()
    assert not errors
    assert len(results)==2 and results[0]==results[1]
    assert results[0].status=="completed"


def test_denied_physical_execution_from_manual_plan():
    sdk=EnergyChain.demo()
    user=sdk.principal("developer", allowed_sites={"demo-site"})
    sdk.tools.register(ToolSpec("unsafe-demo", "must not execute",
                                Permission.EXECUTE,lambda *,site_id:{"sent":True}))
    bad=IntelligencePlan("bad",1,(ToolStep("action","unsafe-demo"),))
    with pytest.raises(PlanRejected):
        sdk.intelligence().run(task="run action",plan=bad,
                               principal=user,site_id="demo-site")


def test_failed_step_blocks_following_tools():
    sdk=EnergyChain.demo()
    user=sdk.principal("developer", allowed_sites={"demo-site"})
    def fails(*,site_id):
        raise RuntimeError("provider token secret intentionally not returned")
    sdk.tools.register(ToolSpec("failure-demo","deliberate failure",Permission.READ,fails))
    plan=IntelligencePlan("error",1,(
        ToolStep("first","failure-demo"),
        ToolStep("never","get_asset_state",{"asset_id":"demo-load","metric":"power_w"}),
    ))
    report=sdk.intelligence().run(task="failure",principal=user,site_id="demo-site",plan=plan)
    assert report.status=="failed"
    assert [s.status for s in report.steps]==["failed","blocked"]
    assert report.error_code=="RuntimeError"
    assert "provider token" not in str(report)
    assert not report.outputs


def test_model_cannot_claim_to_have_called_tools_without_execution():
    class Model:
        def generate(self, system, user, context):
            return json.dumps({"id":"ai-task","version":1,"steps":[
                {"id":"x","tool":"unknown-tool","arguments":{}}]})
    sdk=EnergyChain.demo()
    user=sdk.principal("developer",allowed_sites={"demo-site"})
    with pytest.raises(PlanRejected):
        sdk.intelligence(model=Model()).run(
            task="Make something up",principal=user,site_id="demo-site",
            allowed_tools={"get_asset_state"})
