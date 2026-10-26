from datetime import datetime, timezone
import math
import pytest
from energychain import (EnergyReading, Metric, EnergySite, EnergyAsset, AssetKind,
                         estimate_battery_runtime, estimate_energy_cost, Tariff, simple_average_forecast)
from energychain.exceptions import ValidationError

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def test_reading_metadata_units():
    r = EnergyReading("a", Metric.POWER_W, 123.4, NOW, "meter")
    assert r.unit == "W" and r.quality == "measured"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, 101.0])
def test_soc_rejects_invalid(value):
    with pytest.raises(ValidationError):
        EnergyReading("a", Metric.STATE_OF_CHARGE_PCT, value, NOW, "source")


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        EnergyReading("a", Metric.POWER_W, 4, datetime(2026, 1, 1), "source")


def test_battery_runtime_and_cost():
    result = estimate_battery_runtime(10000, 70, 1000, reserve_pct=20)
    assert result.hours == pytest.approx(4.5)
    assert estimate_energy_cost(2000, Tariff(100, "NGN")) == 200
    assert estimate_battery_runtime(10000, 70, 0).hours is None


def test_simple_forecast_is_baseline():
    r = [EnergyReading("a", Metric.POWER_W, n, NOW, "source") for n in [100, 300]]
    assert simple_average_forecast(r, 3) == [200, 200, 200]
