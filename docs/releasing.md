# Publishing the `energychain` distribution

For each new release, confirm official PyPI availability and smoke-test the distribution in a clean environment before announcing that version. The existing releases include v0.1.0, v0.2.0 and v0.3.0.

## Existing license and prior release

The source repository is https://github.com/energychainai/energychain. Before any change from private to public, complete [the open-source launch checklist](open-source-launch-checklist.md).
EnergyChain v0.1.0 was published on October 26, 2026. Do not overwrite the tag
or attempt to upload the same version or filenames to PyPI.

The owner chose the MIT License, and `main` contains the approved `LICENSE`,
`[project].license = "MIT"`, `license-files = ["LICENSE"]`, and the
`setuptools>=77` build requirement. Keep all of these in subsequent releases.
The distribution wheel **and source archive** are publicly downloadable
regardless of whether the development GitHub repository is public or private.

## Version policy

The current published SDK is v0.3.0, with v0.1.0 and v0.2.0 retained. The steps below apply to a future version and must be updated for that version.
Keep the `pyproject.toml` version, `energychain.__version__`, the new release tag and wheel/source metadata identical.
Any subsequent functionality must land in a separately reviewed release.

## Account setup (existing publisher; verify before release)

After transferring this repository from `Atanseiye` to the `energychainai` organization, update the existing PyPI project's Trusted Publisher settings to match the new owner and repository before tagging another release. This account-level change is not accomplished by editing `publish.yml`. Do not trigger a new release while the old publisher trust is still configured.

1. Confirm the currently published version at `https://pypi.org/pypi/energychain/json` and ensure the planned new version does not already exist. Never overwrite a published version.
2. Sign in at https://pypi.org/manage/account/publishing/ and confirm the existing GitHub
   Trusted Publisher with these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI project | `energychain` |
   | GitHub owner | `energychainai` |
   | Repository | `energychain` |
   | Workflow filename | `publish.yml` |
   | Environment | `pypi` |

   Check the existing `energychain` project's Publishing settings; do not register or claim a new project.
3. In repository **Settings → Environments**, verify the existing `pypi` environment.
   Configure deployment rules/reviewers supported by the account as appropriate.
   The workflow grants `id-token: write` only to the isolated publishing job;
   no PyPI password or long-lived token belongs in the repository or its secrets.

These account checks require authenticated owner access. A committed workflow does
not independently prove the Trusted Publisher or environment configuration.

## Validate the release commit

```bash
python -m pip install -e '.[dev]'
python -m ruff check --isolated --select E4,E7,E9,F src tests scripts examples
python -m pytest -q
python -m build
python -m twine check --strict dist/*
python scripts/check_dist.py --tag vX.Y.Z --require-license
```

Start with an empty `dist/` directory. `python -m build` builds the wheel from the
source archive, and `check_dist.py` checks that both contain the same SDK and
matching name/version metadata. The license check is mandatory for publishing.
Do not omit `--require-license` in an official release: this project already uses MIT.

Install the built wheel into a new virtualenv with `--no-index --no-deps`, then run
`python -I scripts/smoke_test.py` using that environment's Python. `-I` prevents the
checkout or `PYTHONPATH` from masking an incomplete wheel. CI does this on Python
3.10–3.13 on Linux and Python 3.12 on Windows.

## Publish and prove installation

1. Ensure the exact release commit is on `main`, its CI is green, licensing is
   settled, the source has passed the publication audit and PyPI/account setup is complete.
2. Create and publish a non-prerelease GitHub Release tagged `vX.Y.Z` at that commit, with the actual new version.
   `.github/workflows/publish.yml` repeats CI, verifies main ancestry and tag/version
   agreement, validates licensing and tests the exact wheel before uploading.
3. The separate `publish` job obtains short-lived PyPI credentials through GitHub
   OIDC and publishes the previously tested artifacts. Actions are pinned to full
   commit hashes. No code build or checkout runs in the OIDC-enabled job.
4. The `verify` job runs `python scripts/verify_pypi.py`. It checks official PyPI
   metadata and SHA256 hashes against the tested artifacts, creates a new Python
   environment, and performs an **unpinned** install of `energychain` using only
   `https://pypi.org/simple/`, without cache, local wheels or extra indexes. It checks
   the installed version, official download URL, wheel hash, imports and SDK smoke
   behavior. Success is reported only after that check passes.

If upload succeeds but verification fails, inspect the verification error before
retrying. PyPI release filenames cannot be overwritten. After a successful upload,
rerun only the failed verification job rather than uploading the same files again.

**PyPI distributions are public independently of GitHub visibility.** Published wheels/sdists and their source can generally be downloaded by anyone. Check redistributability before every release.

## Provider and document-feature verification

Run all provider contract mocks, protected document format parsers and tenant/site
isolation tests. The core distribution must remain dependency-free; optional
models and documents extras must be metadata-scoped. Only a non-prerelease GitHub
Release from tested main may trigger the existing PyPI Trusted Publisher.
