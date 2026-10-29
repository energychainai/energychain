# Security policy

EnergyChain is an alpha-stage developer SDK, not a certified energy-equipment controller. Current integrations are read-only/advisory by default. Production applications must supply their own authentication, tenant isolation, secret management, monitoring and operational controls. See [docs/security.md](docs/security.md) for the technical threat model.

## Supported versions

| Version | Security fixes |
| --- | --- |
| Latest published 0.3.x | Best-effort security fixes |
| 0.2.x and 0.1.x | Not routinely maintained; upgrade |

## Privately report a vulnerability

**Do not create a public issue or pull request containing exploit details, credentials or sensitive customer data.**

Use [GitHub's private vulnerability reporting](https://github.com/energychainai/energychain/security/advisories/new) when enabled. If that path is unavailable, contact the maintainer through a non-public contact method listed on their GitHub profile; do not post the exploit publicly merely to request a contact channel.

Include the affected version, a minimized reproduction using synthetic data, plausible impact, and suggested mitigation if known. Do not test against equipment or systems without authorization.

We will review valid reports and coordinate a fix and disclosure where possible. Response timelines are not guaranteed for this volunteer-maintained alpha project. If a real credential has leaked, rotate or revoke it with its provider immediately; deleting the latest file does not remove it from Git history.

## Safety boundaries

- Never treat LLM or document output as authorization to operate physical equipment.
- Require explicit scope checking for site data and privileged actions.
- Use synthetic data in public examples and tests.
- Treat files and third-party connectors as untrusted inputs.
- Do not publish operational secrets, meter identifiers, customer records or internal infrastructure details.

Maintainers should enable GitHub private vulnerability reporting, repository secret scanning and push protection where available before making the repository public.
