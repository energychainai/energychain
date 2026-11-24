"""Offline tests for binding Cloud model settings to an application's provider."""
from __future__ import annotations

from email.message import Message
from io import BytesIO
import json
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from energychain._cloud_client import CLOUD_ORIGIN, STAGING_ORIGIN, CloudError
from energychain.cloud_applications import CloudApplications
from energychain.model_gateway import ModelGateway


APP_ID = "1" * 32
APP_TOKEN = "a" * 43
PROVIDER_KEY = "local-provider-fixture-key"
MODEL_NAME = "reviewed-model"
CONFIGURED = {"enabled": True, "provider": "openai", "model": MODEL_NAME}
DISABLED = {"enabled": False, "provider": None, "model": None}
MODEL_REPLY = {
    "choices": [{"message": {"content": "42 kWh"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 4},
}


class CloudOpener:
    def __init__(self, payload, *, error_status=None):
        self.payload = payload
        self.error_status = error_status
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append(request)
        assert timeout > 0
        headers = Message()
        headers["Content-Type"] = "application/json"
        response = BytesIO(json.dumps(self.payload).encode())
        if self.error_status is not None:
            raise HTTPError(request.full_url, self.error_status, "Fixture rejection", headers, response)
        response.headers = headers
        response.status = 200
        return response


def test_cloud_selection_uses_the_existing_model_gateway_and_local_credential():
    opener = CloudOpener(CONFIGURED)
    provider = Mock()
    provider.post.return_value = MODEL_REPLY
    other_adapter = Mock()
    traces = []

    def create_openai_gateway(model):
        return ModelGateway("openai", model, api_key=PROVIDER_KEY, transport=provider,
                            on_trace=traces.append)

    adapter = Mock(side_effect=create_openai_gateway)
    binding = CloudApplications(APP_ID, APP_TOKEN, opener=opener)
    gateway = binding.model_gateway({"openai": adapter, "anthropic": other_adapter})

    adapter.assert_called_once_with(MODEL_NAME)
    other_adapter.assert_not_called()
    provider.post.assert_not_called()
    (request,) = opener.requests
    assert request.full_url == f"{CLOUD_ORIGIN}/v1/applications/{APP_ID}/llm"
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == f"Bearer {APP_TOKEN}"
    assert request.data is None
    assert PROVIDER_KEY not in repr(request.header_items())

    assert isinstance(gateway, ModelGateway)
    result = gateway.complete(system="Be concise.", user="What was the total?")
    assert result.text == "42 kWh"
    assert result.model == MODEL_NAME
    assert result.usage.total_tokens == 14
    (endpoint, payload, headers, _timeout), _ = provider.post.call_args
    assert endpoint == "https://api.openai.com/v1/chat/completions"
    assert payload["model"] == MODEL_NAME
    assert headers["Authorization"] == f"Bearer {PROVIDER_KEY}"
    assert APP_TOKEN not in repr((endpoint, payload, headers))
    assert traces[0].success is True
    assert PROVIDER_KEY not in repr(traces)


def test_disabled_selection_does_not_build_a_gateway():
    opener = CloudOpener(DISABLED)
    adapter = Mock()
    binding = CloudApplications(APP_ID, APP_TOKEN, origin=STAGING_ORIGIN, opener=opener)

    assert binding.model_gateway({"openai": adapter}) is None
    adapter.assert_not_called()
    (request,) = opener.requests
    assert request.full_url == f"{STAGING_ORIGIN}/v1/applications/{APP_ID}/llm"


def test_application_resolves_azure_selection_with_its_compatible_gateway():
    binding = CloudApplications(
        APP_ID, APP_TOKEN, opener=CloudOpener(CONFIGURED | {"provider": "azure-openai"}),
    )

    def build(model):
        return ModelGateway("openai-compatible", model, api_key=PROVIDER_KEY,
                            base_url="https://reviewed-model.example.org/openai/v1", max_retries=0)

    gateway = binding.model_gateway({"azure-openai": build})
    assert gateway.provider == "openai-compatible"
    assert gateway.model == MODEL_NAME


@pytest.mark.parametrize("payload", [
    None,
    {"enabled": True, "provider": "openai"},
    CONFIGURED | {"enabled": 1},
    CONFIGURED | {"provider": "unknown-provider"},
    CONFIGURED | {"model": ""},
    CONFIGURED | {"endpoint": "https://unexpected.example.org/v1"},
    DISABLED | {"provider": "openai", "model": MODEL_NAME},
])
def test_malformed_cloud_settings_do_not_call_adapter(payload):
    adapter = Mock()
    binding = CloudApplications(APP_ID, APP_TOKEN, opener=CloudOpener(payload))

    with pytest.raises(CloudError):
        binding.model_gateway({"openai": adapter, "unknown-provider": adapter})
    adapter.assert_not_called()


def test_configured_provider_requires_its_explicit_local_adapter():
    binding = CloudApplications(APP_ID, APP_TOKEN, opener=CloudOpener(CONFIGURED))
    unrelated_adapter = Mock()

    with pytest.raises(CloudError):
        binding.model_gateway({"anthropic": unrelated_adapter})
    unrelated_adapter.assert_not_called()


@pytest.mark.parametrize("result", [None, MODEL_NAME, "different-model"])
def test_factory_must_return_a_gateway_for_the_configured_model(result):
    binding = CloudApplications(APP_ID, APP_TOKEN, opener=CloudOpener(CONFIGURED))
    if result == "different-model":
        result = ModelGateway("openai", result, api_key=PROVIDER_KEY)
    adapter = Mock(return_value=result)

    with pytest.raises(CloudError):
        binding.model_gateway({"openai": adapter})
    adapter.assert_called_once_with(MODEL_NAME)


def test_cloud_authorization_error_never_invokes_provider_or_exposes_token():
    opener = CloudOpener({"error": "invalid_application_credential"}, error_status=401)
    binding = CloudApplications(APP_ID, APP_TOKEN, opener=opener)
    adapter = Mock()

    with pytest.raises(CloudError) as rejected:
        binding.model_gateway({"openai": adapter})
    assert APP_TOKEN not in str(rejected.value)
    adapter.assert_not_called()


def test_non_cloud_origin_is_rejected_before_sending_the_application_token():
    opener = CloudOpener(CONFIGURED)

    with pytest.raises(CloudError):
        CloudApplications(APP_ID, APP_TOKEN, origin="https://outside.example.org", opener=opener)
    assert not opener.requests
