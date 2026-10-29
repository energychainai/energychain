# Contributing to EnergyChain

Thanks for helping make safe, composable energy software easier to build. EnergyChain is an early-stage MIT-licensed Python SDK. Contributions are welcome, including documentation, tests, bug reports and integrations.

## Before you start

- Read the [code of conduct](CODE_OF_CONDUCT.md), [security policy](SECURITY.md), and [architecture](docs/architecture.md).
- For larger proposals, open a feature issue first to discuss scope and compatibility. For a small fix, a pull request is fine.
- Never submit real meter credentials, customer data, site exports, private API keys, internal utility endpoints, or logs containing sensitive information. Use synthetic fixtures.
- State whether results come from simulation, estimation, or field-validated measurements. Do not describe the SDK as certified for device control.

## Development setup

Use Python 3.10 or newer and a virtual environment:

```bash
git clone https://github.com/Atanseiye/energychain.git
cd energychain
python -m venv .venv
python -m pip install -e '.[dev]'
python -m ruff check --isolated --select E4,E7,E9,F src tests scripts examples
python -m pytest -q
python scripts/check_public_release.py
python -m build
python -m twine check --strict dist/*
```

The core package intentionally has no non-standard-library runtime dependencies. Add optional providers or parsers under clearly named extras and include offline tests with mocked external services.

## Pull requests

1. Fork the repository and create a focused branch from `main`.
2. Add tests for behavioral changes and document any user-facing API change.
3. Keep external network access, device dispatch, and privileged actions opt-in. Preserve existing authorization and safety boundaries.
4. Run the checks above; ensure no real credentials or private data appear in files or Git history.
5. Open a pull request explaining the change, tests, compatibility implications and safety considerations. A maintainer reviews before merging.

Keep changes small when practical. Maintainers may request revisions or decline changes that make energy-system controls less safe.

## Licensing and attribution

By submitting a contribution, you agree that your contribution is offered under this repository's MIT License and that you have the right to submit it. No copyright assignment or contributor license agreement is required. Contributors retain their own copyrights. Git commit authorship and the project history provide contributor credit; see [AUTHORS.md](AUTHORS.md).

## Reporting problems

Use the issue templates for non-sensitive bugs and features. For a vulnerability or exposed credential, follow [SECURITY.md](SECURITY.md), not a public issue.
