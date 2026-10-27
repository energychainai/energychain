# EnergyChain Document Intelligence — v0.3.0

EnergyChain accepts local **PDF, DOCX, TXT, Markdown, CSV and XLSX** files. It extracts text, headings, page/row/sheet provenance and explicitly stated energy quantities, then chunks and indexes content in a tenant-bound, site-scoped SQLite knowledge base.

## Installation

~~~bash
python -m pip install 'energychain[documents]==0.3.0'
~~~

The documents extra supplies pypdf, python-docx and openpyxl. TXT, Markdown, CSV, SQLite FTS5 keyword search and the default document index do not need other runtime dependencies.

## Local ingestion and scoped retrieval

~~~python
from energychain import EnergyKnowledgeBase, Principal, Permission
index = EnergyKnowledgeBase(
    "tenant-knowledge.sqlite3", tenant_id="utility-customer-acme",
    allowed_root="/srv/acme/manuals",
)
operator = Principal(
    "operator-123", frozenset({"site-17"}),
    frozenset({Permission.READ, Permission.ANALYZE, Permission.PREPARE}),
)
stored = index.ingest_file(
    "/srv/acme/manuals/battery.pdf", principal=operator, site_id="site-17",
)
for match in index.search("battery reserve current", principal=operator,
                          site_id="site-17", limit=5):
    print(match.citation, match.source_sha256, match.energy_facts, match.text)
~~~

The tenant_id must originate from **trusted backend authentication**, not a user parameter or LLM response. PREPARE allows ingest/delete; READ allows query/list/answer. Every query is filtered to the configured tenant and authorized site. Duplicate uploads are idempotent, with SHA256 source fingerprint.

## Optional embeddings and agent context

~~~python
def embed_texts(texts: list[str]) -> list[list[float]]:
    # Connect your permitted embedding model or hosted service.
    raise NotImplementedError

index = EnergyKnowledgeBase("data.sqlite", tenant_id="tenant",
                             embedder=embed_texts)
context, sources = index.context_for(
    "What is the stated battery current?",
    principal=operator, site_id="site-17",
)
answer = index.answer(
    "Which current is explicitly documented?",
    model=gateway, principal=operator, site_id="site-17",
)
print(answer.answer, answer.sources)
~~~

Embeddings are developer-controlled and batched (up to 64 chunks). All returned embeddings must be numeric, finite, consistent dimensional vectors. Avoid mixing embedding models in one existing index. Retrieval blends lexical overlap with cosine similarity. These scores rank relevance, **not factual validity**.

Each RetrievedPassage carries filename, SHA256, section, page for PDF, sheet for XLSX, chunk ID and evidence quantities. The answer exposes those retrieved passages as citations; it does not independently certify every generated statement. Energy facts are unverified extracted claims (Wh/kWh, W/kW, V/A/Hz, percentages and ₦/$).

## Security and production checklist

- Authenticate tenant, user, site permissions at your API ingress. Do not give an LLM arbitrary access to tenant_id, document uploads or physical energy tools.
- Limit upload size and file types upstream, screen malware, and run untrusted PDF/Office extraction in a separate unprivileged process with CPU/memory/time limits. Built-in parser limits are **not a sandbox**.
- Typical defaults: 20 MB file, 1M extracted characters, 500 PDF pages, 20k rows, 100 columns, 30 sheets, 80 MB uncompressed Office ZIP and 20k chunks per site.
- File ingestion requires allowed_root and rejects symlinks/path traversal. ingest_bytes is available for carefully authenticated uploads after application-side screening.
- Password-protected PDFs and unsupported formats are refused. Scanned PDFs need external OCR. Excel formulas are not executed and workbook external links are not fetched.
- Do not store database/backups unencrypted on shared hosts; manage encryption, retention, backups, user deletion requests and resource monitoring at deployment level.
- Optional embedding providers may receive document text; enforce data-residency and vendor privacy requirements.
- Document text and retrieved excerpts are untrusted **data**, never system instructions, device control permissions or verified field measurements.
- The SQLite FTS5 keyword index has an authorized fallback when FTS5 is unavailable. Large distributed fleets should use an audited, access-filtered managed index.

See examples/document_intelligence.py and tests/test_document_intelligence.py.
