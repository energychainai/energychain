# Transfer EnergyChain to the official GitHub organization

The canonical repository should be `https://github.com/energychainai/energychain`. Preserve the existing GitHub repository ID, Git history, MIT license, issues, releases and package identity. **Do not create a new repository or fork as a replacement.**

## Transfer (owner action)

1. Sign into GitHub as `Atanseiye`. Confirm that you have permission to create repositories in the `energychainai` organization, that there is no existing `energychain` repository there, and that you remain an owner of the organization.
2. Keep `Atanseiye/energychain` **private** while completing the transfer.
3. Open `https://github.com/Atanseiye/energychain/settings`, scroll to **Danger Zone** and select **Transfer ownership**.
4. Choose `energychainai` as the destination organization, leave the repository name `energychain` unchanged, confirm the name and finish the transfer.
5. Check that the repository now loads at `https://github.com/energychainai/energychain` and retains its original history, tags, PRs and collaborators. Do not create another repository at the original URL because GitHub redirects may be lost.

## Finish the technical cutover

1. Merge the migration PR **after transfer** so the official repository URLs and `.github/workflows/publish.yml` match `energychainai/energychain`.
2. In the existing PyPI project `energychain` (not a new project), update the Trusted Publisher to:
   - Owner: `energychainai`
   - Repository: `energychain`
   - Workflow: `publish.yml`
   - GitHub environment: `pypi`
   Any old `Atanseiye/energychain` publisher should be removed only after verifying the replacement. Do not publish a new tag or release until trusted publishing is repaired and tested.
3. In GitHub repository Settings → Environments, verify the `pypi` environment, reviewers and deployment restrictions. Confirm the workflow has access to the environment.
4. In GitHub organization Settings, install/authorize the GitHub app/connector needed to manage the transferred repository. Confirm repository access is scoped appropriately and not unexpectedly public.
5. Turn on private vulnerability reporting, secret scanning and push protection where available. Review branch rulesets and the open-source launch checklist before changing visibility.
6. In local clones run:

   ```bash
   git remote set-url origin https://github.com/energychainai/energychain.git
   git remote -v
   ```

7. Check CI on `main`, source/issue links, README links, private advisory link and current package metadata. The existing `energychain` PyPI distribution remains the same project; metadata URLs for already released distributions can remain historical until the next legitimate package release.

**Safety:** Transferring ownership does not automatically make a repository public. Keep it private until the rights, secrets/history, Action logs and licensing reviews are complete.
