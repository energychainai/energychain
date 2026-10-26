from datetime import datetime, timedelta, timezone
import pytest
from energychain import (EnergyChain, EnergyReading, Metric, PlanningSlot, FlexibleLoad,
                         optimize_load_schedule, energy_balance, estimate_pv_power)
from energychain.exceptions import ValidationError
from energychain.tools.extended import _integrate_power

T=datetime(2026,10,26,10,tzinfo=timezone.utc)

def test_power_integral_rejects_gaps_and_unsorted_dup():
    seq=[EnergyReading("load",Metric.POWER_W,1000,T,"test"),
         EnergyReading("load",Metric.POWER_W,2000,T+timedelta(hours=1),"test")]
    assert _integrate_power(seq)==1500
    with pytest.raises(ValidationError):
        _integrate_power([seq[0],seq[1],seq[1]])
    with pytest.raises(ValidationError):
        _integrate_power([seq[0],EnergyReading("load",Metric.POWER_W,1000,T+timedelta(hours=3),"test")])


def test_scheduling_finds_optimal_window():
    slots=[PlanningSlot(T+timedelta(hours=i),solar_w=0,base_load_w=100,
                        tariff_per_kwh=[100,1,100][i]) for i in range(3)]
    plan=optimize_load_schedule(slots,[FlexibleLoad("heater",1000,1,0,3)],
                                max_site_power_w=1500)
    assert plan.starts=={"heater":1}
    assert plan.optimized_grid_cost < plan.baseline_grid_cost
    assert plan.evaluated_schedules==3


def test_planning_infeasible_and_combination_bound():
    slots=[PlanningSlot(T+timedelta(hours=i),0,800,1) for i in range(5)]
    with pytest.raises(ValidationError):
        optimize_load_schedule(slots,[FlexibleLoad("heating",300,1,0,5)],max_site_power_w=1000)
    with pytest.raises(ValidationError):
        optimize_load_schedule(slots,[FlexibleLoad("a",100,1,0,5)],max_site_power_w=1000,
                               max_evaluations=4)


def test_pv_energy_balance_and_constraint_tool():
    assert estimate_pv_power(1000,4000,performance_ratio=.8)==3200
    assert energy_balance(2000,2500,200).deficit_w==300
    c=EnergyChain.demo()
    user=c.principal("dev",allowed_sites={"demo-site"})
    result=c.tools.invoke("check_energy_constraints",user,"demo-site",arguments={
        "values":{"reserve":20},"limits":[{"key":"reserve","lower":25,"upper":100,"unit":"%"}]})
    assert not result["valid"]
    assert len(c.tools.describe()) >= 18
