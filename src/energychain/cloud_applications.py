"""Opt-in bindings between Cloud application settings and the local ModelGateway."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import re

from ._cloud_client import CLOUD_ORIGIN, CloudClient, CloudError, CloudHTTPError
from .model_gateway import ModelGateway


_APPLICATION_ID = re.compile(r"[0-9a-f]{32}")
_APPLICATION_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_PROVIDERS = frozenset((*ModelGateway.providers(), "azure-openai", "custom"))
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}")


class CloudApplications:
    """Read one application's model selection over EnergyChain Cloud HTTPS."""

    def __init__(self, application_id: str, token: str, *, origin: str = CLOUD_ORIGIN, opener=None):
        if not isinstance(application_id, str) or not _APPLICATION_ID.fullmatch(application_id):
            raise CloudError("Enter a valid Cloud application ID.")
        if not isinstance(token, str) or not _APPLICATION_TOKEN.fullmatch(token):
            raise CloudError("Enter a valid Cloud application credential.")
        self._client = CloudClient(origin=origin, opener=opener)
        self._path = f"/v1/applications/{application_id}/llm"
        self._token = token

    def model_gateway(self, adapters: Mapping[str, Callable[[str], ModelGateway]]) -> ModelGateway | None:
        """Fetch the current selection, then resolve it using a local adapter factory."""
        try:
            config = self._client._request("GET", self._path, token=self._token)
        except CloudHTTPError as error:
            if error.status == 401:
                raise CloudError("Cloud rejected this application's credential.") from None
            raise
        if config is None or set(config) != {"enabled", "provider", "model"} or type(config["enabled"]) is not bool:
            raise CloudError("Cloud returned invalid application model settings.")
        provider, model = config["provider"], config["model"]
        if not config["enabled"] and provider is None and model is None:
            return None
        if (not config["enabled"] or not isinstance(provider, str) or provider not in _PROVIDERS
                or not isinstance(model, str) or not _MODEL.fullmatch(model)):
            raise CloudError("Cloud returned invalid application model settings.")
        build = adapters.get(provider)
        if not callable(build):
            raise CloudError("The configured provider is not approved by this application.")
        gateway = build(model)
        if not isinstance(gateway, ModelGateway) or gateway.model != model:
            raise CloudError("The application adapter did not use the configured model.")
        return gateway
