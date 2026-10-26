"""Read a real Home Assistant energy entity. No commands are sent.

Set ENERGYCHAIN_HA_URL (HTTPS origin), ENERGYCHAIN_HA_TOKEN and ENERGYCHAIN_HA_ENTITY.
The entity must report unit_of_measurement 'W' and numeric state. Supply your own sensor.
"""
import os
from energychain import (EnergyChain, HomeAssistantConnector, HAEntityMapping,
                         EnergySite, EnergyAsset, AssetKind, Metric, Capability, require_fresh)


def main():
    site = EnergySite("my-home", "Home")
    asset = EnergyAsset("household-load", site.id, "Household electricity load", AssetKind.LOAD,
                        frozenset({Capability.READ}))
    adapter = HomeAssistantConnector(
        site=site, base_url=os.environ["ENERGYCHAIN_HA_URL"],
        token_provider=lambda: os.environ["ENERGYCHAIN_HA_TOKEN"],
        mappings=[HAEntityMapping(asset, os.environ["ENERGYCHAIN_HA_ENTITY"], Metric.POWER_W, "W")])
    sdk = EnergyChain()
    sdk.add_connector("my-home", adapter)
    principal = sdk.principal("local-developer", allowed_sites={site.id})
    reading = sdk.tools.invoke("get_asset_state", principal, site.id,
                               arguments={"asset_id":asset.id, "metric":"power_w"})
    require_fresh(reading, maximum_age_seconds=300)
    print(f"{reading.value} {reading.unit} at {reading.timestamp.isoformat()}; source={reading.source}")


if __name__ == "__main__":
    main()
