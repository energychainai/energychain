# Publishing the `energychain` distribution

**Do not claim `pip install energychain` works until the release exists on https://pypi.org/project/energychain/** and the installed package has been smoke-tested using a clean environment.

## Existing license and prior release

The repository remains private at https://github.com/Atanseiye/energychain.
EnergyChain v0.1.0 was published on October 26, 2026. Do not overwrite the tag
or attempt to upload the same version or filenames to PyPI.

The owner chose the MIT License, and `main` contains the approved `LICENSE`,
`[project].license = "MIT"`, `license-files = ["LICENSE"]`, and the
`setuptools>=77` build requirement. Keep all of these in the v0.2.0 release.
The distribution wheel **and source archive** are publicly downloadable even
though the development GitHub repository remains private.

## Version policy

The deep SDK expansion was released as v0.2.0; this is the next v0.3.0 release, preserving all previous artifacts.
Keep the `pyproject.toml` version, `energychain.__version__`, the release
tag `v0.3.0`, and wheel/source metadata identical.
Any subsequent functionality must land in a separately reviewed release.

## Account setup (existing publisher; verify before release)

1. Confirm the currently published version at `https://pypi.org/pypi/energychain/json` and ensure `0.3.0` does not already exist. Never overwrite a published version.
2. Sign in at https://pypi.org/manage/account/publishing/ and confirm the existing GitHub
   Trusted Publisher with these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI project | `energychain` |
   | GitHub owner | `Atanseiye` |
   | Repository | `energychain` |
   | Workflow filename | `publish.yml` |
   | Environment | `pypi` |

   Check the existing `energychain` project's Publishing settings; do not register or claim a new project.
3. In repository **Settings → Environments**, create `pypi`. Keep the repository
   private. Set deployment rules/reviewers supported by the account as appropriate.
   The workflow grants `id-token: write` only to the isolated publishing job;
   no PyPI password or long-lived token belongs in the repository or its secrets.

These account steps require authenticated owner access. A committed workflow does
not configure the pending publisher in PyPI or verify the environment's settings.

## Validate the release commit

```bash
python -m pip install -e '.[dev]'
python -m ruff check --isolated --select E4,E7,E9,F src tests scripts examples
python -m pytest -q
python -m build
python -m twine check --strict dist/*
python scripts/check_dist.py --tag v0.3.0 --require-license
```

Start with an empty `dist/` directory. `python -m build` builds the wheel from the
source archive, and `check_dist.py` checks that both contain the same SDK and
matching name/version metadata. The license check is mandatory for publishing.
Omit only `--require-license` when checking technical readiness before the owner
has selected terms; that does not authorize a public release.

Install the built wheel into a new virtualenv with `--no-index --no-deps`, then run
`python -I scripts/smoke_test.py` using that environment's Python. `-I` prevents the
checkout or `PYTHONPATH` from masking an incomplete wheel. CI does this on Python
3.10–3.13 on Linux and Python 3.12 on Windows.

## Publish and prove installation

1. Ensure the exact release commit is on `main`, its CI is green, licensing is
   settled and PyPI/account setup is complete.
2. Create and publish a non-prerelease GitHub Release tagged `v0.3.0` at that commit.
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

A **private GitHub repository does not make a PyPI distribution private**. Published wheels/sdists and their source can generally be downloaded by anyone. Decide whether the package source is suitable for public distribution before publishing.

## v0.3-specific verification

Run all provider contract mocks, protected document format parsers and tenant/site
isolation tests. The core distribution must remain dependency-free; optional
models and documents extras must be metadata-scoped. Only a non-prerelease GitHub
Release from tested main may trigger the existing PyPI Trusted Publisher.
