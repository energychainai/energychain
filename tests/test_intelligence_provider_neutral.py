"""Provider-neutral task planning; model account access is never required by SDK tests."""
import json

import pytest

from energychain import EnergyChain, ModelGateway
from energychain.intelligence_runtime import IntelligencePlan, ToolStep


class ModelStub:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def generate(self, system, user, context):
        self.calls += 1
        return self.result


@pytest.mark.parametrize("provider_label", ["groq", "openai", "anthropic", "ollama", "local"])
def test_model_agnostic_planner_uses_injected_textmodel(provider_label):
    """The engine selects no provider: every TextModel implementation has the same contract."""
    model = ModelStub(json.dumps({
        "id": "ai-task",
        "version": 1,
        "steps": [{"id": "load", "tool": "get_asset_state",
                   "arguments": {"asset_id": "demo-load", "metric": "power_w"}}],
    }))
    sdk = EnergyChain.demo()
    principal = sdk.principal("model-test", allowed_sites={"demo-site"})
    engine = sdk.intelligence(model=model)
    result = engine.run(
        task=f"Review site load with {provider_label} adapter",
        site_id="demo-site",
        principal=principal,
        allowed_tools={"get_asset_state"},
    )
    assert result.status == "completed"
    assert model.calls == 1
    assert result.evidence[0].tool == "get_asset_state"


def test_sdk_does_not_choose_a_default_model_or_require_api_key(monkeypatch):
    for name in ("GROQ_API_KEY", "OPENAI_API_KEY", "ENERGYCHAIN_LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    sdk = EnergyChain.demo()
    engine = sdk.intelligence()
    assert engine.model is None
    principal = sdk.principal("model-test", allowed_sites={"demo-site"})
    result = engine.run(
        task="Offline read",
        principal=principal,
        site_id="demo-site",
        plan=IntelligencePlan("offline", 1, (
            ToolStep("load", "get_asset_state",
                     {"asset_id": "demo-load", "metric": "power_w"}),
        )),
    )
    assert result.status == "completed"
    assert result.interpretation_status == "not_requested"


def test_groq_compatible_gateway_only_when_explicitly_configured():
    """No credentials embedded or network requests issued by this test."""
    gateway = ModelGateway(
        "openai-compatible", "openai/gpt-oss-20b",
        base_url="https://api.groq.com/openai/v1",
        api_key="injected-test-token-placeholder",
    )
    assert gateway.provider == "openai-compatible"
    assert gateway.base_url == "https://api.groq.com/openai/v1"
