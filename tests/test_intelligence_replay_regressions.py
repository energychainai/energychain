"""Release regressions for current authorization, typed inputs and model replay."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from energychain import EnergyChain, Permission
from energychain.exceptions import PermissionDenied
from energychain.intelligence_runtime import (
    InputRef, IntelligencePlan, OutputRef, RunConflict, SQLiteIntelligenceStore, ToolStep,
    EvidenceError, as_dict, to_json,
)
from energychain.tools import ToolSpec


def analysis_plan():
    return IntelligencePlan("balance", 1, (
        ToolStep("balance", "calculate_energy_balance", {"solar_w": 1000, "load_w": 500}),
    ))


@pytest.mark.parametrize("restriction", ["permission", "blocked_action"])
def test_cached_analysis_rechecks_current_authorization(tmp_path, restriction):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    with SQLiteIntelligenceStore(tmp_path / "runs.sqlite") as store:
        engine = sdk.intelligence(store=store)
        request = dict(task="Check balance", principal=principal, site_id="demo-site",
                       plan=analysis_plan(), run_id="balance-run")
        initial = engine.run(**request)
        assert initial.status == "completed"
        if restriction == "permission":
            request["principal"] = replace(principal, permissions=frozenset({Permission.READ}))
        else:
            sdk.tools.policy.blocked_actions = frozenset({"calculate_energy_balance"})
        with pytest.raises(PermissionDenied):
            engine.run(**request)
        fresh = engine.run(**{**request, "run_id": "fresh-balance-run"})
        assert fresh.error_code == "PermissionDenied"


def test_cached_result_cannot_reuse_a_broader_principal_site_scope(tmp_path):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site", "other-site"})
    with SQLiteIntelligenceStore(tmp_path / "runs.sqlite") as store:
        engine = sdk.intelligence(store=store)
        request = dict(task="Check balance", principal=principal, site_id="demo-site",
                       plan=analysis_plan(), run_id="scope-run")
        assert engine.run(**request).status == "completed"
        with pytest.raises(RunConflict):
            engine.run(**{**request, "principal": replace(
                principal, allowed_sites=frozenset({"demo-site"}))})


def test_datetime_input_refs_reach_real_history_tools_as_datetimes():
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=3)
    plan = IntelligencePlan("history", 1, (
        ToolStep("history", "get_energy_history", {
            "asset_id": "demo-load", "metric": "power_w",
            "start": InputRef("start"), "end": InputRef("end"),
        }),
    ))
    result = sdk.intelligence().run(task="Read history", principal=principal,
                                    site_id="demo-site", plan=plan,
                                    inputs={"start": start, "end": end})
    assert result.status == "completed"
    assert result.outputs["history"]
    assert result.steps[0].arguments["start"] == start.isoformat()
    json.dumps(result.outputs)


def test_typed_output_refs_preserve_datetimes_without_exposing_secret_fields():
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    instant = datetime.now(timezone.utc)
    captured = []

    def clock(*, site_id):
        return {"timestamp": instant, "api_key": "test-placeholder"}

    def check(*, site_id, when, payload):
        assert isinstance(when, datetime)
        assert payload["api_key"] == "[REDACTED]"
        captured.append(when)
        return {"ok": True}

    sdk.tools.register(ToolSpec("clock", "Synthetic clock", Permission.READ, clock))
    sdk.tools.register(ToolSpec("check-time", "Check typed time", Permission.READ, check))
    plan = IntelligencePlan("clock-check", 1, (
        ToolStep("clock", "clock"),
        ToolStep("check", "check-time", {
            "when": OutputRef("clock", ("timestamp",)), "payload": OutputRef("clock"),
        }),
    ))
    result = sdk.intelligence().run(task="Check time", principal=principal,
                                    site_id="demo-site", plan=plan)
    assert result.status == "completed"
    assert captured == [instant]
    assert result.outputs["clock"]["api_key"] == "[REDACTED]"
    assert result.outputs["clock"]["timestamp"] == instant.isoformat()


class ChangingModel:
    def __init__(self):
        self.calls = 0
        self.offline = False

    def generate(self, *args):
        self.calls += 1
        if self.offline:
            raise RuntimeError("test provider is unavailable")
        return json.dumps({"id": "ai-task", "version": 1, "steps": [{
            "id": "load" + str(self.calls), "tool": "get_asset_state",
            "arguments": {"asset_id": "demo-load", "metric": "power_w"},
        }]})


@pytest.mark.parametrize("offline", [False, True])
def test_completed_model_run_replays_across_reopen_without_another_provider_call(tmp_path, offline):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    model = ChangingModel()
    request = dict(task="Read load", principal=principal, site_id="demo-site",
                   allowed_tools={"get_asset_state"}, run_id="model-run")
    path = tmp_path / "runs.sqlite"
    with SQLiteIntelligenceStore(path) as store:
        initial = sdk.intelligence(model=model, store=store).run(**request)
        assert initial.status == "completed"
    model.offline = offline
    with SQLiteIntelligenceStore(path) as store:
        replay = sdk.intelligence(model=model, store=store).run(**request)
        assert replay == initial
        assert model.calls == 1
        with pytest.raises(RunConflict):
            sdk.intelligence(model=model, store=store).run(**{**request, "task": "Different task"})
        assert model.calls == 1


def test_model_cache_rechecks_policy_before_exposing_results(tmp_path):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    model = ChangingModel()
    with SQLiteIntelligenceStore(tmp_path / "runs.sqlite") as store:
        engine = sdk.intelligence(model=model, store=store)
        request = dict(task="Read load", principal=principal, site_id="demo-site",
                       allowed_tools={"get_asset_state"}, run_id="blocked-model-run")
        assert engine.run(**request).status == "completed"
        sdk.tools.policy.blocked_actions = frozenset({"get_asset_state"})
        with pytest.raises(PermissionDenied):
            engine.run(**request)
        assert model.calls == 1


def test_failed_model_proposal_does_not_reserve_an_unfinished_run(tmp_path):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    model = ChangingModel()
    request = dict(task="Read load", principal=principal, site_id="demo-site",
                   allowed_tools={"get_asset_state"}, run_id="retry-proposal")
    with SQLiteIntelligenceStore(tmp_path / "runs.sqlite") as store:
        engine = sdk.intelligence(model=model, store=store)
        model.offline = True
        with pytest.raises(RuntimeError):
            engine.run(**request)
        model.offline = False
        assert engine.run(**request).status == "completed"


def test_datetime_and_text_inputs_do_not_share_a_cached_request(tmp_path):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    instant = datetime.now(timezone.utc)
    plan = IntelligencePlan("preferences", 1, (ToolStep("prefs", "get_preferences"),))
    with SQLiteIntelligenceStore(tmp_path / "runs.sqlite") as store:
        engine = sdk.intelligence(store=store)
        request = dict(task="Read preferences", principal=principal, site_id="demo-site",
                       plan=plan, inputs={"when": instant}, run_id="typed-request")
        assert engine.run(**request).status == "completed"
        with pytest.raises(RunConflict):
            engine.run(**{**request, "inputs": {"when": instant.isoformat()}})


@pytest.mark.parametrize("step_id", ["token", "api_key", "authorization"])
def test_structural_step_ids_survive_persistence_and_json_adapters(tmp_path, step_id):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    sdk.tools.register(ToolSpec("payload", "Synthetic output", Permission.READ,
                                lambda *, site_id: {"value": 7, "api_key": "test-placeholder"}))
    plan = IntelligencePlan("structural-ids", 1, (ToolStep(step_id, "payload"),))
    with SQLiteIntelligenceStore(tmp_path / "runs.sqlite") as store:
        engine = sdk.intelligence(store=store)
        request = dict(task="Read payload", principal=principal, site_id="demo-site",
                       plan=plan, run_id="structural-id-run")
        initial = engine.run(**request)
        replay = engine.run(**request)
        expected = {step_id: {"value": 7, "api_key": "[REDACTED]"}}
        assert initial.outputs == replay.outputs == expected
        assert replay == initial
        assert as_dict(initial)["outputs"] == expected
        assert json.loads(to_json(initial))["outputs"] == expected


@pytest.mark.parametrize("stale", [False, True])
def test_freshness_validates_readings_beyond_the_provenance_summary(stale):
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    now = datetime.now(timezone.utc)
    reading = {"asset_id": "demo-load", "metric": "power_w", "value": 1,
               "source": "test", "quality": "observed", "timestamp": now.isoformat()}
    last = {**reading, "timestamp": (now - timedelta(days=10)).isoformat()} if stale else reading
    sdk.tools.register(ToolSpec("many-readings", "Synthetic history", Permission.READ,
                                lambda *, site_id: [reading] * 200 + [last]))
    plan = IntelligencePlan("many-readings", 1, (ToolStep("history", "many-readings"),))
    result = sdk.intelligence(max_input_age_seconds=60).run(
        task="Validate history", principal=principal, site_id="demo-site", plan=plan)
    if stale:
        assert result.status == "failed"
        assert result.error_code == "EvidenceError"
        assert not result.outputs
    else:
        assert result.status == "completed"
        assert len(result.outputs["history"]) == 201
        assert len(result.evidence[0].observed_sources) == 200


def test_freshness_cannot_skip_deeply_nested_readings():
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    payload = {"asset_id": "demo-load", "metric": "power_w", "value": 1,
               "source": "test", "quality": "observed",
               "timestamp": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()}
    for _ in range(17):
        payload = {"nested": payload}
    sdk.tools.register(ToolSpec("nested-reading", "Synthetic history", Permission.READ,
                                lambda *, site_id: payload))
    plan = IntelligencePlan("nested-reading", 1, (ToolStep("history", "nested-reading"),))
    result = sdk.intelligence(max_input_age_seconds=60).run(
        task="Validate history", principal=principal, site_id="demo-site", plan=plan)
    assert result.status == "failed"
    assert result.error_code == "EvidenceError"


def test_cached_readings_must_still_meet_the_current_freshness_limit(tmp_path, monkeypatch):
    from energychain.intelligence_runtime import engine as runtime

    class Clock(datetime):
        current = datetime.now(timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz)

    monkeypatch.setattr(runtime, "datetime", Clock)
    sdk = EnergyChain.demo()
    principal = sdk.principal("operator", allowed_sites={"demo-site"})
    reading = {"asset_id": "demo-load", "metric": "power_w", "value": 1,
               "source": "test", "quality": "observed", "timestamp": Clock.current.isoformat()}
    sdk.tools.register(ToolSpec("reading", "Synthetic history", Permission.READ,
                                lambda *, site_id: reading))
    plan = IntelligencePlan("freshness-replay", 1, (ToolStep("history", "reading"),))
    with SQLiteIntelligenceStore(tmp_path / "runs.sqlite") as store:
        engine = sdk.intelligence(store=store, max_input_age_seconds=60)
        request = dict(task="Validate reading", principal=principal, site_id="demo-site",
                       plan=plan, run_id="freshness-run")
        assert engine.run(**request).status == "completed"
        Clock.current += timedelta(minutes=2)
        with pytest.raises(EvidenceError):
            engine.run(**request)
