"""Reproducible, model-independent forecast and operational-evidence evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt, isfinite
from statistics import fmean
from energychain.exceptions import ValidationError


@dataclass(frozen=True)
class ForecastEvaluation:
    sample_count: int
    mae: float
    rmse: float
    bias: float
    mape_pct: float | None
    mape_evaluated: int
    # All values are in the same input unit; do not compare W and Wh.


def evaluate_forecast(actual: list[float], forecast: list[float]) -> ForecastEvaluation:
    if not actual or len(actual) != len(forecast):
        raise ValidationError("actual and forecast vectors must be nonempty and equal length")
    if any(not isfinite(x) for x in (*actual, *forecast)):
        raise ValidationError("forecast evaluation requires finite values")
    errors = [p - y for y, p in zip(actual, forecast)]
    ape = [abs(p - y)/abs(y)*100 for y,p in zip(actual,forecast) if y != 0]
    return ForecastEvaluation(len(actual), fmean(abs(x) for x in errors),
                              sqrt(fmean(x*x for x in errors)), fmean(errors),
                              fmean(ape) if ape else None, len(ape))


@dataclass(frozen=True)
class BacktestResult:
    train_samples: int
    test_samples: int
    baseline: float
    metrics: ForecastEvaluation


def chronological_mean_backtest(values: list[float], *, test_fraction: float = .25) -> BacktestResult:
    """Train on earlier samples and evaluate only on later holdout observations."""
    if (len(values) < 4 or not 0 < test_fraction < .5 or
        any(not isfinite(x) for x in values)):
        raise ValidationError("invalid chronological backtest input")
    test_count = max(1, round(len(values)*test_fraction))
    split = len(values) - test_count
    train, test = values[:split], values[split:]
    prediction = fmean(train)
    return BacktestResult(len(train), len(test), prediction,
                          evaluate_forecast(test, [prediction]*len(test)))
