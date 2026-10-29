# Public open-source launch checklist

This checklist is a publication gate, not evidence that every item has already been verified. Keep the repository private until the maintainer reviews and checks each item.

## Rights and repository contents

- [ ] Confirm all code, documentation, examples, logos, datasets and third-party contributions may be redistributed under their respective terms.
- [ ] Confirm MIT licensing is intentional and that creator/contributor attribution in AUTHORS.md is accurate.
- [ ] Review the complete Git history, tags and historical workflows for secrets, personal information, customer data, proprietary code, internal endpoints and accidental attachments. Current-file scanning alone is insufficient.
- [ ] Audit GitHub Actions logs, artifacts, release notes, issues and pull requests for accidentally exposed data; public visibility affects more than the default branch.
- [ ] Review commit author names and email privacy preferences. Existing commit metadata becomes public.

## Security

- [ ] Rotate or revoke every credential that might have been committed or displayed in a log, even if later removed.
- [ ] If sensitive data exists in history, rewrite all affected branches/tags with a coordinated plan and notify collaborators before making the repository public. Consider PyPI-published source archives separately, because public artifacts cannot simply be taken back.
- [ ] Ensure `.env*`, local database files, private keys, provider configuration files and customer/site exports are untracked and excluded by .gitignore.
- [ ] Run `python scripts/check_public_release.py --history` from a complete, unshallow clone. Supplement with a mature secret scanner; automated matches cannot prove an absence of secrets.
- [ ] Enable GitHub secret scanning, push protection and private vulnerability reporting where available.
- [ ] Add an appropriate main-branch ruleset requiring passing CI, reviews and controlled releases. Check that PyPI Trusted Publishing and the `pypi` environment remain intact.

## Developer onboarding

- [ ] Merge CONTRIBUTING, security, governance, issue/PR templates and links from README.
- [ ] Verify a clean `pip install energychain` and the pinned v0.3.0 examples; CI test builds independently.
- [ ] Confirm documentation links and current homepage/domain resolve before changing PyPI metadata.
- [ ] Check that docs distinguish simulated data, read-only integrations and planned managed infrastructure from field-tested capabilities.
- [ ] Run CI against the final release-readiness commit and inspect results.

## Organization migration

- [ ] Transfer the existing GitHub repository (rather than creating a replacement) to `energychainai` while it is still private.
- [ ] Install/authorize the connected GitHub integration for `energychainai` and grant access to `energychain`.
- [ ] Verify original maintainer access, Actions/CI and release-environment permissions under the new organization.
- [ ] Update the existing PyPI Trusted Publisher to `energychainai/energychain` with workflow `publish.yml` and environment `pypi`, before publishing any new version.
- [ ] Update local Git remotes, external links, and repository metadata without creating a new repository at the old redirect location.

## Publication and community

- [ ] Change GitHub repository visibility to Public through repository settings after the above items are accepted.
- [ ] Recheck source visibility, code download, MIT License, links, issue forms and private vulnerability channel from a signed-out browser.
- [ ] Add accurate project topics, description and website URL to repository About.
- [ ] Announce the open-source repository, invite external contributors and collect measurable public usage evidence.
- [ ] Apply to appropriate OpenAI open-source support programs; eligibility and any API credits are discretionary, not automatic.

Current maintainer: [@Atanseiye](https://github.com/Atanseiye).
