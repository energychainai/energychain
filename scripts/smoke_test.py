"""Exercise an installed distribution. Run with python -I in a clean virtualenv."""
from datetime import datetime, timezone
from importlib.metadata import distribution
import json
from pathlib import Path
import tempfile

import energychain
from energychain import (
    Approval, AssetKind, CSVConnector, EnergyAsset, EnergyChain, EnergySite,
    Permission, Principal, SQLiteEnergyMemory, ToolRegistry, ToolSpec,
    SignedApprovalAuthority,
)
from energychain.exceptions import ApprovalRequired, PermissionDenied


def smoke_test():
    installed = distribution("energychain")
    assert installed.metadata["Name"] == "energychain"
    assert installed.version == energychain.__version__
    assert Path(energychain.__file__).resolve().is_relative_to(
        Path(installed.locate_file("")).resolve()), "import resolved outside installed distribution"
    assert not any("extra ==" not in r for r in (installed.requires or []))
    for name in energychain.__all__:
        assert hasattr(energychain, name), name
    chain = EnergyChain.demo()
    user = chain.principal("smoke", allowed_sites={"demo-site"})
    assert len(chain.tools.invoke("discover_assets", user, "demo-site")) == 4
    state = chain.tools.invoke("get_battery_state", user, "demo-site",
                               arguments={"asset_id": "demo-battery"})
    assert state["state_of_charge"].quality == "simulated"
    assert chain.tools.invoke("estimate_energy_cost", user, "demo-site",
                              arguments={"energy_wh": 2000, "price_per_kwh": 100})["cost"] == 200
    try:
        chain.tools.invoke("discover_assets", user, "other-site")
    except PermissionDenied:
        pass
    else:
        raise AssertionError("cross-site access was allowed")
    tools = ToolRegistry()
    tools.register(ToolSpec("act", "test-only command", Permission.EXECUTE,
                            lambda *, site_id: site_id))
    operator = Principal("operator", frozenset({"site"}), frozenset({Permission.EXECUTE}))
    try:
        tools.invoke("act", operator, "site")
    except ApprovalRequired:
        pass
    else:
        raise AssertionError("execution did not require approval")
    try:
        tools.invoke("act", operator, "site",
                     approval=Approval("operator", "site", "act", True))
    except ApprovalRequired:
        pass
    else:
        raise AssertionError("unsigned approval unexpectedly authorized execution")
    authority = SignedApprovalAuthority(b"2" * 32)
    tools.policy.approval_authority = authority
    signature = authority.issue(operator, "site", "act")
    assert tools.invoke("act", operator, "site", approval=signature) == "site"
    with tempfile.TemporaryDirectory() as directory:
        csv = Path(directory) / "readings.csv"
        csv.write_text("asset_id,metric,value,timestamp,source\n"
                       "load,power_w,100,2026-10-25T10:00:00Z,export\n", encoding="utf-8")
        connector = CSVConnector.from_csv(
            csv, site=EnergySite("site", "Site"),
            assets=[EnergyAsset("load", "site", "Load", AssetKind.LOAD)])
        reading = connector.read("load", "power_w")
        assert reading.value == 100
        database = Path(directory) / "readings.db"
        with SQLiteEnergyMemory(database) as memory:
            memory.add_reading("site", reading)
            memory.set_preference("site", "reserve_pct", 20)
        with SQLiteEnergyMemory(database) as memory:
            assert memory.preferences("site") == {"reserve_pct": 20}
            assert memory.history("site", "load", "power_w",
                                  datetime(2026, 10, 25, tzinfo=timezone.utc),
                                  datetime(2026, 10, 26, tzinfo=timezone.utc)) == [reading]
    print(json.dumps({"name": installed.metadata["Name"], "version": installed.version,
                      "import_path": energychain.__file__, "smoke_test": "passed"}, indent=2))


if __name__ == "__main__":
    smoke_test()
