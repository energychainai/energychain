"""Opt-in solar irradiance forecast source (weather forecast, NOT PV output)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Callable
from urllib.parse import urlencode
from energychain.exceptions import ValidationError
from energychain.integrations.http import get_json
from energychain.models import ensure_aware


@dataclass(frozen=True)
class IrradiancePoint:
    timestamp: datetime
    global_horizontal_w_m2: float
    source: str = "open-meteo"
    quality: str = "forecast"


class OpenMeteoIrradiance:
    """Third-party forecast dependency; verify provider licensing for commercial use."""
    def __init__(self, transport: Callable[..., object] = get_json) -> None:
        self._transport = transport

    def hourly(self, latitude: float, longitude: float, *, days: int = 2) -> list[IrradiancePoint]:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180 and
                isfinite(latitude) and isfinite(longitude) and 1 <= days <= 14):
            raise ValidationError("invalid coordinates or forecast horizon")
        query = urlencode({"latitude":latitude, "longitude":longitude,
                           "hourly":"shortwave_radiation", "forecast_days":days,
                           "timezone":"UTC"})
        result = self._transport("https://api.open-meteo.com/v1/forecast?" + query)
        if not isinstance(result, dict) or not isinstance(result.get("hourly"), dict):
            raise ValidationError("weather provider returned malformed response")
        hour = result["hourly"]
        times, values = hour.get("time"), hour.get("shortwave_radiation")
        if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values):
            raise ValidationError("weather forecast arrays mismatch")
        if len(times) > days*24 + 24:
            raise ValidationError("weather forecast exceeds expected bounds")
        points=[]
        for ts, val in zip(times, values):
            try:
                stamp = datetime.fromisoformat(ts + "+00:00" if isinstance(ts, str) and len(ts)==16 else ts)
                ensure_aware(stamp)
                value = float(val)
            except (ValueError, TypeError) as exc:
                raise ValidationError("invalid forecast observation") from exc
            if not isfinite(value) or value < 0:
                raise ValidationError("irradiance forecast out of range")
            points.append(IrradiancePoint(stamp, value))
        return points
