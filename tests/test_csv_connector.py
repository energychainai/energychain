from datetime import datetime, timezone
import pytest
from energychain import CSVConnector, EnergySite, EnergyAsset, AssetKind, Metric, EnergyChain
from energychain.exceptions import ValidationError


def test_csv_connector_real_export(tmp_path):
    file = tmp_path / "readings.csv"
    file.write_text("asset_id,metric,value,timestamp,source\nbattery-a,state_of_charge_pct,70,2026-10-25T10:00:00+00:00,export\nbattery-a,state_of_charge_pct,75,2026-10-25T11:00:00+00:00,export\n", encoding="utf-8")
    site = EnergySite("site-a", "Solar site")
    asset = EnergyAsset("battery-a", "site-a", "Main battery", AssetKind.BATTERY)
    c = CSVConnector.from_csv(file, site=site, assets=[asset])
    chain = EnergyChain()
    chain.add_connector("csv", c)
    principal = chain.principal("owner", allowed_sites={"site-a"})
    reading = chain.tools.invoke("get_asset_state", principal, "site-a", arguments={"asset_id": "battery-a", "metric": "state_of_charge_pct"})
    assert reading.value == 75 and reading.quality == "measured"
    assert len(c.history("battery-a", Metric.STATE_OF_CHARGE_PCT, datetime(2026,10,25,tzinfo=timezone.utc), datetime(2026,10,26,tzinfo=timezone.utc))) == 2


def test_csv_rejects_invalid_timestamp(tmp_path):
    file = tmp_path / "bad.csv"
    file.write_text("asset_id,metric,value,timestamp,source\na,power_w,30,2026-10-25T10:00:00,export\n")
    with pytest.raises(ValidationError):
        CSVConnector.from_csv(file, site=EnergySite("site", "Site"), assets=[EnergyAsset("a", "site", "A", AssetKind.LOAD)])


@pytest.mark.parametrize("timestamp", ["2026-10-25T10:00:00Z", "2026-10-25T11:00:00+01:00"])
def test_csv_supports_iso_utc_and_offsets(tmp_path, timestamp):
    file = tmp_path / "utc.csv"
    file.write_text(
        "asset_id,metric,value,timestamp,source\n"
        f"a,power_w,30,{timestamp},export\n", encoding="utf-8")
    connector = CSVConnector.from_csv(
        file, site=EnergySite("site", "Site"),
        assets=[EnergyAsset("a", "site", "A", AssetKind.LOAD)])
    assert connector.read("a", Metric.POWER_W).timestamp == datetime(
        2026, 10, 25, 10, tzinfo=timezone.utc)
