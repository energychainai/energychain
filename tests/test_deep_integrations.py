from datetime import datetime, timezone
import pytest
from energychain import (EnergySite, EnergyAsset, AssetKind, Metric,
                         HomeAssistantConnector, HAEntityMapping, OpenMeteoIrradiance,
                         EnergyChain, HybridSiteSimulator, Fleet, Principal)
from energychain.exceptions import PermissionDenied, ValidationError, UnsupportedCapability
from energychain.integrations.http import get_json

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def test_home_assistant_realistic_mapping_and_unit_conversion():
    site = EnergySite("house", "Residence")
    asset = EnergyAsset("solar-main", "house", "PV", AssetKind.SOLAR)
    observed = []
    def transport(url, *, token):
        observed.append((url, token))
        return {"entity_id":"sensor.solar_power", "state":"1.25",
                "attributes":{"unit_of_measurement":"kW"}, "last_updated":"2026-10-26T11:57:00Z"}
    adapter = HomeAssistantConnector(site=site, base_url="https://home.example.com",
                                    token_provider=lambda:"secret", transport=transport,
                                    mappings=[HAEntityMapping(asset, "sensor.solar_power", Metric.POWER_W, "kW")])
    result = adapter.read("solar-main", Metric.POWER_W)
    assert result.value == 1250 and result.unit == "W"
    assert result.source == "home-assistant" and result.quality == "measured"
    assert observed == [("https://home.example.com/api/states/sensor.solar_power", "secret")]
    with pytest.raises(UnsupportedCapability):
        adapter.history("solar-main", Metric.POWER_W, NOW, NOW)


@pytest.mark.parametrize("url", ["http://localhost:8123", "https://host.invalid/path", "https://person:pwd@host.example"])
def test_connector_rejects_unapproved_base_url(url):
    with pytest.raises(ValidationError):
        HomeAssistantConnector(site=EnergySite("home", "Home"), mappings=[
            HAEntityMapping(EnergyAsset("battery", "home", "Battery", AssetKind.BATTERY),
                            "sensor.soc", Metric.STATE_OF_CHARGE_PCT, "%")],
                               base_url=url, token_provider=lambda:"secret")


def test_home_assistant_rejects_entity_or_unit_spoofing():
    site = EnergySite("home", "Home")
    asset = EnergyAsset("load", "home", "Load", AssetKind.LOAD)
    def bad(*args, **kwargs):
        return {"entity_id":"sensor.incorrect", "state":"500",
                "attributes":{"unit_of_measurement":"W"}, "last_updated":"2026-10-26T12:00:00Z"}
    conn = HomeAssistantConnector(site=site, mappings=[HAEntityMapping(asset,"sensor.load",Metric.POWER_W,"W")],
                                  base_url="https://home.example.com",token_provider=lambda:"secret",transport=bad)
    with pytest.raises(ValidationError):
        conn.read("load", Metric.POWER_W)


def test_weather_source_utc_irradiance_values():
    seen = []
    def http(url):
        seen.append(url)
        return {"hourly":{"time":["2026-10-27T08:00","2026-10-27T09:00"],
                          "shortwave_radiation":[150,300]}}
    source = OpenMeteoIrradiance(transport=http)
    points = source.hourly(7.25, 5.2, days=2)
    assert [p.global_horizontal_w_m2 for p in points] == [150,300]
    assert points[0].timestamp.tzinfo is not None
    assert "latitude=7.25" in seen[0]
    with pytest.raises(ValidationError):
        source.hourly(100,0)


def test_external_transport_requires_https_before_network():
    with pytest.raises(ValidationError):
        get_json("http://169.254.169.254/latest/meta-data/")


def test_fleet_access_requires_all_sites_and_records_partial_failures():
    c = EnergyChain.demo()
    frozen = HybridSiteSimulator(site_id="second", clock=lambda:NOW)
    c.add_connector("second", frozen)
    c.fleets.register(Fleet("two", frozenset({"second", "demo-site"})))
    restricted = Principal("dev", frozenset({"second"}))
    with pytest.raises(PermissionDenied):
        c.fleets.snapshot("two", restricted, Metric.POWER_W, now=NOW)
    # Demo simulator default clock may differ, so set wide allowable age.
    full = Principal("all", frozenset({"second","demo-site"}))
    snapshot = c.fleets.snapshot("two",full,Metric.POWER_W,max_age_seconds=24*3600,now=NOW)
    assert snapshot.fleet_id == "two" and len(snapshot.observations) >= 2
    assert snapshot.failures  # batteries have no POWER_W metric
    with pytest.raises(PermissionDenied):
        c.tools.invoke("get_fleet_snapshot", restricted, "second",
                       arguments={"fleet_id":"two", "metric":"power_w"})
