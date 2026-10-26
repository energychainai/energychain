from datetime import datetime, timedelta, timezone
import pytest
from energychain import (EnergyChain, Principal, Permission, Approval,
                         ToolSpec, ToolRegistry, CallableTextModel, HybridSiteSimulator)
from energychain.exceptions import PermissionDenied, ApprovalRequired, ValidationError


def test_demo_connectors_tools_and_history():
    c = EnergyChain.demo()
    principal = c.principal("test-user", allowed_sites={"demo-site"})
    items = c.tools.invoke("discover_assets", principal, "demo-site")
    assert len(items) == 4
    charge = c.tools.invoke("get_battery_state", principal, "demo-site", arguments={"asset_id": "demo-battery"})
    assert 0 <= charge["state_of_charge"].value <= 100
    result = c.tools.invoke("estimate_battery_runtime", principal, "demo-site", arguments={"battery_id": "demo-battery", "load_w": 900})
    assert result["hours"] > 0
    assert result["quality"] == "estimated"
    assert c.tracer.events("demo-site")


def test_cross_site_access_is_rejected():
    c = EnergyChain.demo()
    principal = Principal("outsider", frozenset({"other-site"}))
    with pytest.raises(PermissionDenied):
        c.tools.invoke("get_battery_state", principal, "demo-site", arguments={"asset_id": "demo-battery"})
    local = Principal("client", frozenset({"demo-site"}))
    with pytest.raises(PermissionDenied):
        c.tools.invoke("get_asset_state", local, "fake-site", arguments={"asset_id": "demo-battery", "metric": "power_w"})


def test_execution_needs_specific_approval_and_permission():
    tools = ToolRegistry()
    tools.register(ToolSpec("turn_on", "simulate command", Permission.EXECUTE, lambda *, site_id: "ok"))
    principal = Principal("owner", frozenset({"demo-site"}), frozenset({Permission.EXECUTE}))
    with pytest.raises(ApprovalRequired):
        tools.invoke("turn_on", principal, "demo-site")
    with pytest.raises(ApprovalRequired):
        tools.invoke("turn_on", principal, "demo-site", approval=Approval("owner", "wrong", "turn_on", True))
    approved = Approval("owner", "demo-site", "turn_on", True)
    assert tools.invoke("turn_on", principal, "demo-site", approval=approved) == "ok"


def test_llm_is_pluggable_but_cannot_choose_tool():
    c = EnergyChain.demo()
    person = c.principal("dev", allowed_sites={"demo-site"})
    llm = CallableTextModel(lambda system, user, context: "simulated response " + context[:30])
    response = c.agent(llm).run("battery charge?", principal=person, site_id="demo-site",
                                tool_name="get_battery_state", tool_arguments={"asset_id": "demo-battery"})
    assert response.answer.startswith("simulated response")
    assert response.tool_result["state_of_charge"].quality == "simulated"


def test_simulator_history_and_clock():
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    sim = HybridSiteSimulator(clock=lambda: now)
    read = sim.read("demo-solar", "power_w")
    assert read.value == 3800.0
    series = sim.history("demo-solar", "power_w", now - timedelta(hours=3), now)
    assert len(series) == 4
    with pytest.raises(ValidationError):
        sim.history("demo-solar", "power_w", now, now-timedelta(hours=1))


def test_multiple_sites_are_isolated_even_when_asset_is_known():
    c = EnergyChain.demo()
    c.add_connector("second", HybridSiteSimulator(site_id="other-site"))
    assert len(c.connectors.assets()) == 8
    first_only = Principal("first", frozenset({"demo-site"}))
    with pytest.raises(PermissionDenied):
        c.tools.invoke("get_asset_state", first_only, "demo-site", arguments={
            "asset_id": "other-site-battery", "metric": "state_of_charge_pct"})
    permitted = Principal("second", frozenset({"other-site"}))
    assert c.tools.invoke("get_asset_state", permitted, "other-site", arguments={
        "asset_id": "other-site-battery", "metric": "state_of_charge_pct"}).value > 0


def test_simulator_values_are_independent_of_timestamp_offset():
    instant = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    offset = timezone(timedelta(hours=5, minutes=30))
    utc = HybridSiteSimulator(clock=lambda: instant)
    local = HybridSiteSimulator(clock=lambda: instant.astimezone(offset))
    assert utc.read("demo-solar", "power_w").value == local.read("demo-solar", "power_w").value
    assert [r.value for r in utc.history("demo-solar", "power_w", instant, instant)] == [
        r.value for r in local.history(
            "demo-solar", "power_w", instant.astimezone(offset), instant.astimezone(offset))]


def test_registry_rejects_duplicate_sites_within_one_connector():
    class DuplicateSiteConnector(HybridSiteSimulator):
        def sites(self):
            return [self.site, self.site]

        def assets(self, site_id):
            return []

    c = EnergyChain()
    with pytest.raises(ValidationError, match="duplicate site id"):
        c.add_connector("ambiguous", DuplicateSiteConnector())
    assert c.connectors.sites() == []
