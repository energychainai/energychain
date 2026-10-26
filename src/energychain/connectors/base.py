"""Connector contract for vendor APIs, device gateways, and simulators."""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from energychain.models import EnergyAsset, EnergyReading, EnergySite, Metric
from energychain.exceptions import UnsupportedCapability


class EnergyConnector(ABC):
    @abstractmethod
    def sites(self) -> list[EnergySite]: ...

    @abstractmethod
    def assets(self, site_id: str) -> list[EnergyAsset]: ...

    @abstractmethod
    def read(self, asset_id: str, metric: Metric) -> EnergyReading: ...

    @abstractmethod
    def history(self, asset_id: str, metric: Metric, start: datetime, end: datetime) -> list[EnergyReading]: ...

    def execute(self, asset_id: str, command: str, parameters: dict) -> dict:
        raise UnsupportedCapability("connector is read-only")
