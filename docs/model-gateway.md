# EnergyChain Model Gateway — v0.3.0

EnergyChain offers a consistent **synchronous TextModel-compatible** API for six provider families. It does not host models, provide API credentials or guarantee any named model is supported by the external service. The caller explicitly selects a provider and model.

| Provider | Identifier | Credential | Backend | Structured outputs |
|---|---|---|---|---|
| OpenAI | openai | OPENAI_API_KEY | official Chat Completions | json_schema response format |
| Anthropic | anthropic | ANTHROPIC_API_KEY | Messages API | output_config.format |
| Gemini | gemini | GEMINI_API_KEY | Google generateContent | generationConfig.responseFormat |
| Hugging Face | huggingface | HF_TOKEN | Inference Providers router | model-dependent OpenAI-compatible |
| Ollama | ollama | none | local loopback /api/chat | format schema |
| HTTPS compatible | openai-compatible | ENERGYCHAIN_LLM_API_KEY | explicitly configured HTTPS server | model/server-dependent |

## Installation

~~~bash
python -m pip install 'energychain[models]==0.3.0'
export OPENAI_API_KEY='your-server-side-key'
~~~

~~~python
from energychain import ModelGateway
gateway = ModelGateway("openai", "gpt-4o-mini", timeout=30, max_retries=2)
result = gateway.complete(
    system="Respond carefully about energy equipment. Do not authorize controls.",
    user="What battery current is stated?",
    context="Unverified datasheet: maximum charge current 40 A.",
)
print(result.text, result.usage.input_tokens, result.duration_ms)
~~~

Existing EnergyAgent applications can use model=gateway.as_text_model(). The gateway implements generate(system, user, context).

## Structured outputs

The optional models extra installs jsonschema. Schema validity is checked before submission and the resulting JSON is validated independently of the provider's claimed schema support.

~~~python
schema = {
    "type": "object",
    "properties": {"equipment": {"type": "string"}, "rating_kw": {"type": "number"}},
    "required": ["equipment", "rating_kw"],
    "additionalProperties": False,
}
result = gateway.complete(
    system="Extract stated values only; return JSON.",
    user="Extract the inverter rating.",
    context="Inverter nominal output 5 kW.",
    json_schema=schema,
)
print(result.json_value)
~~~

Provider-specific schema subsets vary and an unsupported model may fail. Validate each chosen model and account in staging; CI tests mock the providers and are **not live account certification**.

## Operational and security boundaries

- Server-only API keys via provider environment variables or explicit injected credentials; never include keys in web clients, logs or trace callbacks.
- Official provider endpoints are host-locked; compatible endpoints need HTTPS and cannot target private IPs or local names. Ollama uses loopback HTTP only.
- The HTTP transport refuses redirects, bounds total prompt length to 400k characters, requests to 2 MB and responses to 4 MB, and enforces 1–180 second timeouts.
- Transient HTTP 408/429/500/502/503/504 may be retried with capped backoff. Upstream retries can cause extra token charges. Apply separate quotas, budgets, rate limits, queues and failover.
- on_trace receives provider/model, usage, duration and error class only. Prompt content, context and credentials are never included by design.
- The gateway does not stream responses, execute tool calls, issue device commands, calculate provider pricing, or provide managed inference hosting.
- Model results and supplied documents remain **untrusted**. EnergyChain authorization and operator-approved safety boundaries remain independent of the model output.

See examples/model_gateway.py and tests/test_model_gateway.py.
