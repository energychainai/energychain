from datetime import datetime, timedelta, timezone
from energychain import (EnergyChain, EnergyReading, EnergyEvent, Metric, MemoryNote,
                         InMemoryEnergyMemory, SQLiteEnergyMemory, WorkflowStep, EnergyWorkflow)

T = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def exercise_memory(db):
    db.add_reading("site-a", EnergyReading("battery", Metric.POWER_W, 100, T, "test"))
    db.add_reading("site-b", EnergyReading("battery", Metric.POWER_W, 200, T, "test"))
    assert [r.value for r in db.history("site-a", "battery", "power_w", T-timedelta(days=1), T)] == [100]
    db.add_event(EnergyEvent("e", "site-a", "warning", "battery low", T))
    assert len(db.events("site-a")) == 1 and len(db.events("site-b")) == 0
    db.remember(MemoryNote("site-a", "note", "solar was unavailable", T))
    assert len(db.recall("site-a", "solar")) == 1
    assert db.recall("site-b", "solar") == []
    db.set_preference("site-a", "reserve_pct", 30)
    assert db.preferences("site-a")["reserve_pct"] == 30
    assert db.preferences("site-b") == {}


def test_in_memory():
    exercise_memory(InMemoryEnergyMemory())


def test_sqlite(tmp_path):
    path = tmp_path / "energy.db"
    with SQLiteEnergyMemory(path) as db:
        exercise_memory(db)
    with SQLiteEnergyMemory(path) as reopened:
        assert reopened.preferences("site-a")["reserve_pct"] == 30
        assert reopened.recall("site-a", "solar")


def test_workflow_success_and_fail_closed():
    c = EnergyChain.demo()
    principal = c.principal("dev", allowed_sites={"demo-site"})
    workflow = EnergyWorkflow(c.tools, [WorkflowStep("discover_assets"),
                                        WorkflowStep("estimate_energy_cost", {"energy_wh": 2000, "price_per_kwh": 50})])
    result = workflow.run(principal, "demo-site")
    assert result.succeeded and result.outputs[1]["cost"] == 100
    fail = EnergyWorkflow(c.tools, [WorkflowStep("discover_assets"), WorkflowStep("nonexistent")]).run(principal, "demo-site")
    assert not fail.succeeded and fail.failed_step == 1
