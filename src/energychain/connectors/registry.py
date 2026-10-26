"""Connector registration and asset routing."""
from energychain.connectors.base import EnergyConnector
from energychain.exceptions import AssetNotFound, ValidationError
from energychain.models import EnergyAsset, EnergySite


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, EnergyConnector] = {}

    def register(self, name: str, connector: EnergyConnector) -> None:
        if not name or name in self._connectors:
            raise ValidationError("connector name must be nonempty and unique")
        if not isinstance(connector, EnergyConnector):
            raise ValidationError("connector must implement EnergyConnector")
        # Reject duplicate site/asset identifiers across providers to avoid ambiguous routing.
        previous_sites = {s.id for s in self.sites()}
        previous_assets = {a.id for a in self.assets()}
        sites = connector.sites()
        new_site_ids = set()
        for site in sites:
            if site.id in previous_sites or site.id in new_site_ids:
                raise ValidationError(f"duplicate site id: {site.id}")
            new_site_ids.add(site.id)
        new_asset_ids = set()
        for site in sites:
            for asset in connector.assets(site.id):
                if asset.site_id != site.id:
                    raise ValidationError(f"connector asset has mismatched site: {asset.id}")
                if asset.id in previous_assets or asset.id in new_asset_ids:
                    raise ValidationError(f"duplicate asset id: {asset.id}")
                new_asset_ids.add(asset.id)
        self._connectors[name] = connector

    def sites(self) -> list[EnergySite]:
        return [s for c in self._connectors.values() for s in c.sites()]

    def assets(self, site_id: str | None = None) -> list[EnergyAsset]:
        return [a for c in self._connectors.values() for s in c.sites()
                if site_id is None or s.id == site_id for a in c.assets(s.id)]

    def route(self, asset_id: str) -> tuple[EnergyConnector, EnergyAsset]:
        for c in self._connectors.values():
            for s in c.sites():
                for a in c.assets(s.id):
                    if a.id == asset_id:
                        return c, a
        raise AssetNotFound(f"asset not found: {asset_id}")

    def site(self, site_id: str) -> EnergySite:
        for site in self.sites():
            if site.id == site_id:
                return site
        raise AssetNotFound(f"site not found: {site_id}")
