"""Run with: python examples/quickstart.py after pip install energychain"""
from energychain import EnergyChain

chain = EnergyChain.demo()
user = chain.principal("example-user", allowed_sites={"demo-site"})
print("Assets:", [asset.name for asset in chain.tools.invoke("discover_assets", user, "demo-site")])
state = chain.tools.invoke("get_battery_state", user, "demo-site",
                           arguments={"asset_id": "demo-battery"})
print("Battery charge:", state["state_of_charge"].value, "% (SIMULATED)")
estimate = chain.tools.invoke("estimate_battery_runtime", user, "demo-site",
                              arguments={"battery_id": "demo-battery", "load_w": 900})
print("Estimated backup hours:", round(estimate["hours"], 2))
response = chain.agent().run("Can the site supply backup power?", principal=user,
                             site_id="demo-site", tool_name="estimate_battery_runtime",
                             tool_arguments={"battery_id": "demo-battery", "load_w": 900})
print(response.answer)
