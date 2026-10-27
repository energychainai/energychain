"""Offline provider contract, payload privacy and endpoint security tests."""
from __future__ import annotations

import json
import pytest
from energychain.model_gateway import (
    ModelGateway, ModelConfigError, ModelResponseError, ModelHTTPError, JsonTransport
)


class Stub:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def post(self, url, payload, headers, timeout):
        self.calls.append((url, payload, headers, timeout))
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize("provider,response,endpoint", [
    ("openai", {"choices": [{"message": {"content": "42 kWh"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4}}, "/chat/completions"),
    ("anthropic", {"content": [{"type": "text", "text": "42 kWh"}],
                   "stop_reason": "end_turn",
                   "usage": {"input_tokens": 10, "output_tokens": 4}}, "/messages"),
    ("gemini", {"candidates": [{"content": {"parts": [{"text": "42 kWh"}]},
                                "finishReason": "STOP"}]}, ":generateContent"),
    ("huggingface", {"choices": [{"message": {"content": "42 kWh"}}]}, "/chat/completions"),
    ("ollama", {"message": {"content": "42 kWh"}, "done": True}, "/api/chat"),
    ("openai-compatible", {"choices": [{"message": {"content": "42 kWh"}}]}, "/chat/completions"),
])
def test_provider_contract(provider, response, endpoint):
    transport = Stub(response)
    kw = {"base_url": "https://models.example.org/v1"} if provider == "openai-compatible" else {}
    gateway = ModelGateway(provider, "test-model", api_key="fake", transport=transport, **kw)
    assert gateway.as_text_model() is gateway
    assert gateway.generate("system", "Question?", "Unverified 40 kWh") == "42 kWh"
    url, body, headers, timeout = transport.calls[0]
    assert url.endswith(endpoint)
    assert timeout == 30
    assert "Untrusted energy context" in json.dumps(body)
    assert gateway.providers() == ("openai", "anthropic", "gemini", "huggingface",
                                    "ollama", "openai-compatible")
    if provider == "ollama":
        assert "Authorization" not in headers
    else:
        assert ("Authorization" in headers or "x-api-key" in headers
                or "x-goog-api-key" in headers)


SCHEMA = {"type": "object", "properties": {"rating_kw": {"type": "number"}},
          "required": ["rating_kw"], "additionalProperties": False}


@pytest.mark.parametrize("provider,response", [
    ("openai", {"choices": [{"message": {"content": '{"rating_kw":5}'}}]}),
    ("anthropic", {"content": [{"type": "text", "text": '{"rating_kw":5}'}],
                   "stop_reason": "end_turn"}),
    ("gemini", {"candidates": [{"content": {"parts": [{"text": '{"rating_kw":5}'}]},
                                "finishReason": "STOP"}]}),
    ("ollama", {"message": {"content": '{"rating_kw":5}'}, "done": True}),
])
def test_structured_output(provider, response):
    fake = Stub(response)
    gw = ModelGateway(provider, "model", api_key="fake", transport=fake)
    result = gw.complete(system="Return JSON", user="Equipment", json_schema=SCHEMA)
    assert result.json_value == {"rating_kw": 5}
    body = fake.calls[0][1]
    if provider == "openai":
        assert body["response_format"]["json_schema"]["strict"] is True
    elif provider == "anthropic":
        assert body["output_config"]["format"]["type"] == "json_schema"
    elif provider == "gemini":
        assert body["generationConfig"]["responseFormat"]["text"]["mimeType"] == "APPLICATION_JSON"
    else:
        assert body["format"] == SCHEMA


def test_schema_is_verified_locally():
    stub = Stub({"choices": [{"message": {"content": '{"rating_kw":"wrong"}'}}]})
    gw = ModelGateway("openai", "model", api_key="fake", transport=stub)
    with pytest.raises(ModelResponseError):
        gw.complete(system="JSON", user="Extract", json_schema=SCHEMA)
    assert len(stub.calls) == 1
    stub.calls.clear()
    with pytest.raises(Exception):
        gw.complete(system="JSON", user="Extract", json_schema={"type": "no"})
    assert not stub.calls


@pytest.mark.parametrize("provider,url", [
    ("openai-compatible", "http://public.example.com/v1"),
    ("openai-compatible", "https://127.0.0.1/v1"),
    ("openai-compatible", "https://10.1.2.3/v1"),
    ("openai-compatible", "https://user:pass@example.com/v1"),
    ("openai-compatible", "https://api.example.com/v1?key=123"),
    ("ollama", "http://remote.example.com:11434"),
    ("openai", "https://third-party.example.com/v1"),
])
def test_bad_endpoints_blocked(provider, url):
    with pytest.raises(ModelConfigError):
        ModelGateway(provider, "model", api_key="fake", base_url=url)


def test_gemini_model_path_injection_rejected():
    with pytest.raises(ModelConfigError):
        ModelGateway("gemini", "../private?key=123", api_key="fake")


def test_no_key_and_no_private_content_in_traces(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ModelConfigError, match="OPENAI_API_KEY"):
        ModelGateway("openai", "model")
    traces = []
    fake = Stub(error=ModelHTTPError(401))
    gw = ModelGateway("openai", "model", api_key="secret", transport=fake, on_trace=traces.append)
    with pytest.raises(ModelHTTPError) as err:
        gw.complete(system="s", user="Private question", context="private meter readings")
    assert "secret" not in str(err.value)
    assert "meter readings" not in repr(traces)
    assert len(fake.calls) == 1 and traces[0].success is False


def test_transient_http_retry(monkeypatch):
    class Flaky(Stub):
        def post(self, *args):
            self.calls.append(args)
            if len(self.calls) == 1:
                raise ModelHTTPError(503)
            return {"choices": [{"message": {"content": "recovered"}}]}
    monkeypatch.setattr("energychain.model_gateway.time.sleep", lambda _: None)
    stub = Flaky()
    result = ModelGateway("openai", "model", api_key="fake", transport=stub,
                          max_retries=1).generate("safe", "Question", "")
    assert result == "recovered" and len(stub.calls) == 2


@pytest.mark.parametrize("payload", [
    {"choices": [{"message": {"content": ""}}]},
    {"choices": [{"message": {"content": "truncated"}, "finish_reason": "length"}]},
    {"choices": [{"message": {"content": "refused", "refusal": "cannot"}}]},
    {"invalid": True},
])
def test_invalid_model_responses(payload):
    model = ModelGateway("openai", "model", api_key="fake", transport=Stub(payload))
    with pytest.raises(ModelResponseError):
        model.complete(system="safe", user="Question")


def test_success_usage_metadata_only():
    traces = []
    fake = Stub({"choices": [{"message": {"content": "ok"}}],
                 "usage": {"prompt_tokens": 8, "completion_tokens": 3}})
    r = ModelGateway("openai", "model", api_key="fake", transport=fake,
                     on_trace=traces.append).complete(system="system", user="Confidential")
    assert r.usage.total_tokens == 11
    assert traces[0].usage.total_tokens == 11
    assert "Confidential" not in repr(traces)


def test_response_limits():
    with pytest.raises(ValueError):
        JsonTransport(0)
