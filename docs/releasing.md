# Publishing the `energychain` distribution

**Do not claim `pip install energychain` works until the release exists on https://pypi.org/project/energychain/** and the installed package has been smoke-tested using a clean environment.

## Owner decisions before the first public release

The repository is the existing **private** https://github.com/Atanseiye/energychain.
Continue its history; do not recreate it or change its visibility.

The owner selected the **MIT License** and approved public SDK distribution on
26 October 2026. `LICENSE` contains the terms; `[project]` declares `license = "MIT"`
and `license-files = ["LICENSE"]`. The build requires `setuptools>=77` for PEP 639
license metadata. Keep the license in both wheels and source archives.

Public distribution includes the wheel **and source archive**. The publishing
workflow fails before upload if the built artifacts lack license metadata/files.
This is an artifact check, not proof of copyright ownership or legal clearance.

## Account setup

1. Check `https://pypi.org/pypi/energychain/json` immediately before publishing.
   A 404 means no published project is visible; it does not guarantee the name is
   reservable. If another party owns it, stop rather than uploading a substitute.
2. Sign in at https://pypi.org/manage/account/publishing/ and add a pending GitHub
   Trusted Publisher with these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI project | `energychain` |
   | GitHub owner | `Atanseiye` |
   | Repository | `energychain` |
   | Workflow filename | `publish.yml` |
   | Environment | `pypi` |

   A pending publisher does not reserve the name. For an existing project owned by
   this account, configure the publisher in that project's Publishing settings.
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
python scripts/check_dist.py --tag v0.1.0 --require-license
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
2. Create and publish a non-prerelease GitHub Release tagged `v0.1.0` at that commit.
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
