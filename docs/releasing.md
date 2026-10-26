# Publishing the `energychain` distribution

**Do not claim `pip install energychain` works until the release exists on https://pypi.org/project/energychain/** and the installed package has been smoke-tested using a clean environment.

1. Decide the distribution licence explicitly (do not assume MIT merely because it is an SDK). Confirm the `energychain` distribution name is available on **real PyPI**. If someone else owns it, choose a different package name; do not upload under someone else's project.
2. Build and test the exact release commit: `python -m pip install -e '.[dev]' && python -m pytest -q && python -m build && python -m twine check dist/*`.
3. Create a **private** GitHub repository named `energychain` and upload the reviewed source. **Do not put API keys or publishing credentials in Git history.** GitHub Actions are available on eligible private repositories.
4. In your PyPI account, go to https://pypi.org/manage/account/publishing/ and configure a pending **GitHub Trusted Publisher** matching:
   - Distribution: `energychain`
   - GitHub owner: `Atanseiye` (only if that is the repo owner)
   - Repository: `energychain`
   - Workflow filename: `publish.yml`
   - GitHub environment: `pypi`
5. In GitHub repository **Settings → Environments**, create `pypi`, and protect deployments if desired. Publishing job uses OIDC; no long-lived PyPI API token is stored in GitHub.
6. Create and publish a GitHub Release tagged `v0.1.0` after checks pass. That triggers `.github/workflows/publish.yml`.
7. Check the GitHub Actions outcome and verify https://pypi.org/project/energychain/0.1.0/. Test in a clean virtualenv: `python -m pip install energychain==0.1.0` then `python -c "import energychain; print(energychain.__version__)"`.

A **private GitHub repository does not make a PyPI distribution private**. Published wheels/sdists and their source can generally be downloaded by anyone. Decide whether the package source is suitable for public distribution before publishing.
