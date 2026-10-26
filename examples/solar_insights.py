"""Synthetic 24-hour solar generation insights without a model or vendor credential."""
from datetime import datetime, timedelta, timezone
from energychain import EnergyChain, simple_average_forecast

chain = EnergyChain.demo()
principal = chain.principal("demo", allowed_sites={"demo-site"})
end = datetime.now(timezone.utc)
readings = chain.tools.invoke("get_energy_history", principal, "demo-site", arguments={
    "asset_id": "demo-solar", "metric": "power_w", "start": end-timedelta(hours=23), "end": end})
forecast = simple_average_forecast(readings, horizon_hours=4)
print("Synthetic hourly readings:", len(readings))
print("Baseline forecast W:", forecast)
print("Warning: simulation and simple mean baseline, not a trained forecast or validated estimate.")
