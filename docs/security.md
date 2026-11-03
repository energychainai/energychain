# EnergyChain v0.4.0 Threat Model and Operational Safety

## Critical distinction: library versus operating system

EnergyChain is a **developer SDK**, not a remotely hosted authorization or device-control platform. Importing this package into a third-party application cannot guarantee tenant isolation, production identity management, safe energy dispatch, or cybersecurity of the host environment. Vendor-neutral energy data is **untrusted input** even when delivered over HTTPS.

## Threat boundaries and current mitigations

| Trust boundary | Threat | Current mitigation | Missing production safeguard |
|---|---|---|---|
| Connector -> framework | Wrong asset identity, wrong units, stale data | Explicit mapping, verified IDs and units, reading timestamps, freshness helper | Hardware identity attestation, operational acceptance tests |
| Public API -> tool | Cross-site data exposure | Principal site permissions + route ownership checks | Hosted identity service, signed tokens, tenant-aware DB policy |
| LLM -> tools | Prompt injection / model attempts device operation | `BoundedEnergyAgent` only invokes READ / ANALYZE tools; allowlist and max calls | Sandboxed application tools, adversarial evaluation, output encoding |
| SDK -> physical device | Unsupported or unapproved actions | Physical dispatch disabled by default; declared bounded parameters; signed one-time approval support | Separate human approver service; shared approval nonce store; command contract certification; independent verifier; field commissioning |
| Energy telemetry -> memory | Replay, stale/future readings | Per-process ID deduplication, age bounds, site ownership | Durable transactional ingestion ledger, authenticated gateway, clock synchronization, at-least-once broker |
| Memory -> model | Historical observations mistaken for current readings | Time-aware records, provenance, context windows | Data retention policy, provenance validation, privacy review, selective deletion across external systems |
| Network -> HA/weather | SSRF, redirect, secret leakage | HTTPS origin validation, fixed routes, redirect refusal, response size limits, no token logging | Egress allowlists, DNS pinning, cert monitoring, vault-managed credentials |
| Workflow -> execution | Retry duplicates action | Checkpointed workflow restricted to READ/ANALYZE | Durable idempotency keys with transactional action outbox |
| Document -> parser/index | Malicious archives, excessive resource use, cross-tenant retrieval | Bounded parsing, guarded Office archives, allowed root and tenant/site checks | Isolated workers, OS resource limits, storage encryption and retention governance |
| Model -> intelligence plan | Fabricated tools, future references or privileged action proposals | Typed finite plans, explicit tool allowlists, per-step authorization and READ/ANALYZE restriction | Host quotas, provider validation, adversarial application testing |
| Intelligence ledger -> replay | Stale results or revoked permissions exposed by retries | Request/scope binding, current authorization recheck, configured freshness recheck; incomplete reservations fail closed | Operator reconciliation, protected durable storage, distributed concurrency and recovery design |
| Event -> intelligence task | Event payload impersonates a trusted identity or delivery is lost | Host-owned principal, rule/event replay identity, required store and error callback | Authenticated durable transport, retry policy, dead-letter handling and operations alerts |

## Default safety policy

- `Principal` objects are constructed by the embedding application; `EnergyChain.principal()` is **demo-only**. Callers must not let arbitrary clients create their own principals or approve site access.
- `Approval` legacy dataclass **is not trusted by default**. `SignedApprovalAuthority` binds principal, site, action, canonical argument digest, short expiry and single-use nonce.
- The HMAC signing secret and `issue()` API must live in a **separate privileged approval service** that records human consent. Process-local nonce tracking must be replaced with durable atomic storage when using multiple workers.
- `ActionService` always starts with physical dispatch disabled. Setting `enable_physical_dispatch=True` is a low-level extension for integrators with their own trusted certified controls, not a production ready feature declaration.
- `ActionOutcome.status == "unverified"` does not mean hardware reached the requested state.
- All equipment manufacturer, interlock, breaker, inverter and battery-controller protections are authoritative. The SDK must never bypass these.
- `HomeAssistantConnector` is **read-only**; the API's last state timestamp does not certify its physical correctness. Access requires TLS at the Home Assistant endpoint or at its authenticated reverse proxy.

## Incident response / audit recommendations

Production services should log request IDs, actor and organizational identity, asset scope, site scope, source freshness, outcome, latency, approval identity, transport request ID, physical acknowledgment and actual post-action reading; redact credentials, protected identifiers, user messages and unnecessary telemetry. Protect log integrity and retention, and document rollback/safe-stop paths per hardware type.

## Policy for release claims

Only claim a production-grade, field-validated integration after end-to-end live testing under an authorized operator, threat modeling, platform and API compliance review, telemetry provenance validation, device/failure-mode safety assessment, availability/latency SLO measurement and incident rehearsal.

## v0.3 model and document boundaries

Model adapters take server-side credentials and emit metadata-only traces.
Model outputs are untrusted and never bypass site/execute permissions.
Document storage is tenant-bound and permission-checked, but the application
must authenticate users, encrypt storage/backups and isolate untrusted document
parsers in resource-constrained workers. Retrieved evidence and citations do not
certify equipment parameters or generated claims.

## v0.4 intelligence evidence boundaries

Only the trusted host may choose a principal and site. `InputRef`, `OutputRef`
and `depends_on` bind earlier tool results or provenance; they do not grant
privileges or prove that independent tools read the same physical sample.
`VerifiedFinding` means a deterministic comparison against a recorded SDK output,
not an independently verified equipment diagnosis. Generated interpretation is
marked `generated_unverified`.

The runtime redacts recognized secret-bearing fields, but callers must keep
credentials out of prompts, task inputs and documents. Fingerprints establish
local consistency; they do not provide hardware attestation, cryptographic
signatures on measurements or a tamper-resistant external audit service.
