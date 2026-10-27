import pytest
from energychain import evaluate_forecast, chronological_mean_backtest
from energychain.exceptions import ValidationError


def test_forecast_quality_metrics_and_zero_handling():
    result=evaluate_forecast([0,100,200],[10,90,210])
    assert result.mae==10 and result.sample_count==3
    assert result.mape_evaluated==2
    assert result.mape_pct==pytest.approx(7.5)
    assert evaluate_forecast([0],[3]).mape_pct is None


def test_backtest_is_chronological_without_leakage():
    result=chronological_mean_backtest([10,10,10,10,100,100,100,100],test_fraction=.25)
    assert result.train_samples==6 and result.test_samples==2
    assert result.baseline==40
    assert result.metrics.mae==60


@pytest.mark.parametrize("actual,forecast", [([],[]),([1],[2,3]),([1,float('nan')],[2,3])])
def test_evaluation_rejects_incomplete_data(actual,forecast):
    with pytest.raises(ValidationError):
        evaluate_forecast(actual,forecast)
