import json
import pytest
from energychain import (EnergyChain, CallableTextModel, SQLiteWorkflowCheckpoints,
                         WorkflowStep, Permission, Principal, ToolSpec)
from energychain.exceptions import PermissionDenied, ToolError


def test_model_can_plan_bounded_read_tools_but_cannot_execute():
    chain=EnergyChain.demo()
    person=chain.principal("dev",allowed_sites={"demo-site"})
    model=CallableTextModel(lambda *args: json.dumps({"steps":[{"name":"get_battery_state","arguments":{
        "asset_id":"demo-battery"}}],"answer":"Will calculate using observed simulator values."}))
    out=chain.planning_agent(model).run("How charged is my battery?",principal=person,site_id="demo-site")
    assert len(out.tool_calls)==1
    assert out.tool_results[0]["state_of_charge"].quality=="simulated"
    assert len(chain.skills.list())==3


def test_planner_does_not_accept_physical_or_unknown_tools():
    chain=EnergyChain.demo()
    chain.tools.register(ToolSpec("physical_command","danger",Permission.EXECUTE,
                                  lambda *,site_id:"not called"))
    user=chain.principal("dev",allowed_sites={"demo-site"})
    model=CallableTextModel(lambda *args: '{"steps":[{"name":"physical_command","arguments":{}}],"answer":"done"}')
    with pytest.raises(ToolError):
        chain.planning_agent(model).run("run device",principal=user,site_id="demo-site")
    model2=CallableTextModel(lambda *args: '{"steps":[{"name":"nonexistent","arguments":{}}],"answer":"done"}')
    with pytest.raises(ToolError):
        chain.planning_agent(model2).run("do anything",principal=user,site_id="demo-site")


def test_checkpointed_workflow_idempotent_and_scope_locked(tmp_path):
    chain=EnergyChain.demo()
    user=chain.principal("owner",allowed_sites={"demo-site"})
    steps=[WorkflowStep("discover_assets"),WorkflowStep("estimate_energy_cost",{
        "energy_wh": 2500,"price_per_kwh":55})]
    with SQLiteWorkflowCheckpoints(tmp_path/"runs.sqlite") as store:
        first=store.run("run-1",chain.tools,steps,user,"demo-site")
        assert first.succeeded and first.outputs[-1]["cost"]==137.5
        n=len(chain.tracer.events("demo-site"))
        second=store.run("run-1",chain.tools,steps,user,"demo-site")
        assert second.succeeded and len(chain.tracer.events("demo-site"))==n
        with pytest.raises(PermissionDenied):
            store.run("run-1",chain.tools,steps,Principal("other",frozenset({"demo-site"})),"demo-site")
        with pytest.raises(PermissionDenied):
            store.run("run-1",chain.tools,[WorkflowStep("get_preferences")],user,"demo-site")


def test_checkpoint_rejects_execute_or_missing_tool(tmp_path):
    chain=EnergyChain.demo()
    chain.tools.register(ToolSpec("exec","test",Permission.EXECUTE,lambda *,site_id:1))
    user=chain.principal("dev",allowed_sites={"demo-site"})
    with SQLiteWorkflowCheckpoints(tmp_path/"runs.sqlite") as store:
        with pytest.raises(PermissionDenied):
            store.run("x",chain.tools,[WorkflowStep("exec")],user,"demo-site")
        with pytest.raises(PermissionDenied):
            store.run("x",chain.tools,[WorkflowStep("unknown")],user,"demo-site")
