"""No external credentials: fleet insights, incident memory and analytical tools."""
from energychain import (EnergyChain, Fleet, HybridSiteSimulator, EnergyEpisode)


def main():
    sdk = EnergyChain.demo()
    sdk.add_connector("secondary", HybridSiteSimulator(site_id="secondary"))
    sdk.fleets.register(Fleet("sample-fleet", frozenset({"demo-site","secondary"})))
    user = sdk.principal("developer", allowed_sites={"demo-site", "secondary"})
    snapshot = sdk.tools.invoke("get_fleet_snapshot", user, "demo-site", arguments={
        "fleet_id":"sample-fleet", "metric":"power_w", "max_age_seconds":3600})
    print("Fleet observations:", len(snapshot["observations"]))
    print("Unsupported/missing readings:", snapshot["failures"])
    sdk.episodes.add(EnergyEpisode("maintenance-1", "demo-site", "maintenance",
                                    "Battery inspection scheduled; not yet completed"))
    context = sdk.tools.invoke("get_energy_context", user, "demo-site", arguments={
        "query":"maintenance"})
    print("Relevant episodes:", context["episodes"])
    balance = sdk.tools.invoke("calculate_energy_balance", user, "demo-site", arguments={
        "solar_w":2400, "load_w":3000, "generator_w":0})
    print("Power balance:", balance)


if __name__ == "__main__":
    main()
