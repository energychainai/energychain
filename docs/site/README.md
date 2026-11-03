# Versioned documentation build

This directory maintains the documentation served at `https://energychain.app/docs/`.
It keeps the existing site's layout and produces a static, self-contained HTML
document with separate release content, navigation, search and API references.

## Build

Fetch the published tags, install the documentation-only dependencies and build:

```bash
git fetch origin --tags
python -m pip install -r docs/site/requirements.txt
python docs/site/build.py --output build/docs/index.html
```

The build also writes `versions.json`, recording each version's exact source
commit and available topics. These dependencies are not SDK runtime dependencies.

Run the DOM integration checks against the generated output with Node 18+:

```bash
npm --prefix docs/site ci
npm --prefix docs/site test -- ../../build/docs/index.html
```

The checks render every version/topic pair, exercise version changes, scoped
search, missing-topic notices, legacy URLs, browser history, code copying and
keyboard/menu state. Visual layout should also be inspected when browser access
is available.

## Version behavior

- `/docs/` and earlier unversioned topic links resolve to the current release.
- `/docs/0.4.0/intelligence-runtime/` opens the current runtime guide.
- `/docs/0.3.0/model-gateway/` opens the tagged Model Gateway guide.
- Earlier versions use their own tagged README, architecture, examples and exports.
- The selector preserves a topic where available. Unavailable topics show an
  explicit availability page and links to releases that contain the topic.
- Search is limited to the selected release. Browser back/forward and direct
  reloads retain the version and topic.
- Installation commands in archived content pin that version. Tagged source
  links and archive banners distinguish historical statements from current facts.

`template-v0.3.0.html` is the previous live site's documentation shell and guide
snapshot. The builder removes its old router, preserves the visual design and
uses the SDK source guides for release-critical API, safety and migration content.
v0.4.0 documentation reads the reviewed Markdown files in this checkout;
historical content and API exports come from immutable published tags.

## Deploy with the existing website

The Vercel project is `energychain`, project ID
`prj_ADEUIwIUkVp7DVXzwCWPKecxXmQY`. Website source, APIs and existing build steps
are preserved. `site-build.mjs` runs the previous site's build steps, then
copies the generated HTML into `docs/index.html` and writes static entry pages
for version/topic URLs. Each entry has the correct release content, selected
version, page title and canonical URL before JavaScript executes. This makes
shared links and reloads independent of the site's older single-topic rewrites.
The `/docs/:path*` rewrite remains available for forward-compatible routing.

Test a staged production build before promoting it. Check current and archived
versions, missing topics, search, code copying, keyboard/mobile navigation,
direct reloads and old unversioned links. Confirm public production routes after
promotion. Do not submit telemetry or customer-facing forms as part of these checks.

## Add a future release

After its SDK publication is independently verified, add the release to
`VERSIONS`, set `LATEST`, and add its new guides and migration notes. Keep the
older release refs unchanged. Build and verify version routing before updating
the website; never relabel current content as an older release.
