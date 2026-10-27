# EnergyChain v0.3.0 — Model Gateway and Document Intelligence

MIT-licensed alpha release built on EnergyChain v0.2.0, which remains available.

## New
- Six explicit LLM adapter families: OpenAI, Anthropic, Gemini, Hugging Face Inference Providers, Ollama and HTTPS OpenAI-compatible endpoints.
- Provider-neutral ModelGateway compatible with existing TextModel, schema-validated JSON outputs, bounded transport, token/latency traces and credential-safe errors.
- PDF, DOCX, TXT, Markdown, CSV and XLSX ingestion with bounded parsers, guarded Office archives, no external fetch/macros/formula execution.
- Tenant/site-scoped SQLite knowledge index, FTS5 keyword retrieval and optional developer-provided semantic embeddings.
- Stable document hashes, page/sheet/section citations, explicitly stated energy values and retrieval-powered agent context.

## Install

~~~bash
python -m pip install energychain==0.3.0
python -m pip install 'energychain[all]==0.3.0'
~~~

The core requires no external runtime dependencies. Optional extras install jsonschema and parsers.

## Boundaries

CI mocks vendor APIs rather than certifying live API keys or every model variant. PDFs and Office files must be processed in isolated resource-constrained workers in production. Retrieval citations do not establish the correctness of generated answers. Physical dispatch remains blocked by default.
