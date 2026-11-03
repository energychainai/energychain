"""Build release-scoped website documentation from tagged SDK sources.

Run from any directory: python docs/site/build.py --output <website>/docs/index.html
The existing website shell is retained; no application API or credential is read.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import re
import subprocess

from bs4 import BeautifulSoup
import markdown

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LATEST = "0.4.0"
VERSIONS = ["0.4.0", "0.3.0", "0.2.0", "0.1.0"]
SOURCE = "https://github.com/energychainai/energychain"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO).decode("utf-8")


def tagged(version: str, path: str) -> str:
    return git("show", f"v{version}:{path}")


def read_doc(version: str, path: str) -> str:
    if version == LATEST and (REPO / path).is_file():
        return (REPO / path).read_text(encoding="utf-8")
    return tagged(version, path)


def codebox(code: str, language: str = "python") -> str:
    return (f'<div class="codebox"><div class="codeheader"><span>{escape(language)}</span>'
            '<button class="copy" data-copy type="button">Copy ↗</button></div>'
            f'<pre><code>{escape(code.rstrip())}</code></pre></div>')


DOC_SLUGS = {"architecture.md": "architecture", "product-architecture-v01.md": "product-architecture",
             "security.md": "safety-actions", "intelligence-runtime.md": "intelligence-runtime",
             "model-gateway.md": "model-gateway", "document-intelligence.md": "document-intelligence",
             "telemetry-opt-in.md": "sdk-telemetry", "versions.md": "versions",
             "upgrading.md": "upgrading", "releasing.md": "releasing"}


def render_md(text: str, version: str, commit: str) -> str:
    if version != LATEST:
        text = re.sub(r"python -m pip install (?:--upgrade )?energychain(?=\s|$)",
                      f"python -m pip install energychain=={version}", text)
    soup = BeautifulSoup(markdown.markdown(text, extensions=["fenced_code", "tables", "toc"]), "html.parser")
    first = soup.find("h1")
    if first:
        first.decompose()
    for pre in list(soup.find_all("pre")):
        code = pre.find("code")
        lang = next((c.removeprefix("language-") for c in (code or pre).get("class", [])
                     if c.startswith("language-")), "text")
        pre.replace_with(BeautifulSoup(codebox((code or pre).get_text(), lang), "html.parser"))
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith(("http:", "https:", "mailto:", "#")):
            continue
        name = href.split("#")[0].split("/")[-1]
        if name in DOC_SLUGS:
            target_version = LATEST if name == "upgrading.md" else version
            link["href"] = f"/docs/{target_version}/{DOC_SLUGS[name]}/" + ("#" + href.split("#", 1)[1] if "#" in href else "")
        elif name.startswith("release-notes-"):
            link["href"] = f"{SOURCE}/blob/{commit}/docs/{name}"
        elif href.endswith(".md"):
            target = href.removeprefix("../")
            if target.startswith("docs/"):
                target = target[5:]
            link["href"] = f"{SOURCE}/blob/{commit}/docs/{target}"
        elif not href.startswith("/"):
            link["href"] = f"{SOURCE}/blob/{commit}/{href.removeprefix('../')}"
    return str(soup)


def api_reference(version: str, commit: str) -> str:
    tree = ast.parse(tagged(version, "src/energychain/__init__.py"))
    exports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            exports.extend(ast.literal_eval(node.value))
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            exports.extend(ast.literal_eval(node.value))
    text = f"# API reference\n\nThese are the public `energychain` exports from the exact v{version} tag.\n\n"
    text += "## Top-level imports\n\n" + ", ".join(f"`{x}`" for x in exports) + ".\n\n"
    text += f"[Read the complete package exports at this release]({SOURCE}/blob/{commit}/src/energychain/__init__.py).\n\n"
    if version == LATEST:
        text += "## EnergyIntelligence API\n\nImport the engine from `energychain`; import the contracts below from `energychain.intelligence_runtime`.\n\n"
        text += "| Contract | Purpose |\n| --- | --- |\n"
        for name, purpose in [
            ("IntelligencePlan", "Named, versioned finite sequence of tool steps and deterministic rules"),
            ("ToolStep", "Step ID, registered tool, arguments and optional earlier-step dependencies"),
            ("InputRef", "Reference to a named task input"),
            ("OutputRef", "Reference to an earlier step output and explicit key/index path"),
            ("EvidenceRule", "Finite numeric comparison; lt, le, gt, ge, eq or ne"),
            ("IntelligenceResult", "Run status, outputs, steps, evidence, findings and interpretation status"),
            ("EvidenceRecord / SourceEvidence", "Serialized result, fingerprints, observed readings and parent evidence links"),
            ("StepRecord / VerifiedFinding", "Execution status and deterministic comparison results"),
            ("SQLiteIntelligenceStore", "Persistent completed-run replay; incomplete reservations fail closed"),
            ("IntelligenceEventRule / IntelligenceEventSubscription", "Trusted in-process event adapter; requires store and error callback"),
            ("IntelligenceError / PlanRejected / RunConflict / EvidenceError", "Runtime, plan, request-identity and evidence errors"),
            ("format_console / to_json / as_dict", "Presentation and machine-readable result adapters"),
        ]:
            text += f"| `{name}` | {purpose} |\n"
        text += "\n### Engine signatures\n\n```python\n"
        engine = ast.parse(tagged(version, "src/energychain/intelligence_runtime/engine.py"))
        cls = next(n for n in engine.body if isinstance(n, ast.ClassDef) and n.name == "EnergyIntelligence")
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name in {"__init__", "run", "register_tool"}:
                text += f"{node.name}({ast.unparse(node.args)})\n"
        text += "```\n\nThe host supplies authenticated principals. Only READ/ANALYZE tools are eligible. `max_steps` defaults to 8 and permits 1–12. A freshness limit is opt-in.\n\n"
        text += "[Complete typed fields and defaults](" + SOURCE + f"/blob/{commit}/src/energychain/intelligence_runtime/contracts.py). "
        text += "[Runtime guide](intelligence-runtime.md).\n"
    return text


def page(slug: str, title: str, group: str, summary: str, body: str) -> dict:
    return dict(slug=slug, title=title, group=group, summary=summary, body=body)


def from_doc(version: str, commit: str, slug: str, title: str, group: str, path: str) -> dict:
    return page(slug, title, group, f"Release-specific guidance for EnergyChain v{version}.",
                render_md(read_doc(version, path), version, commit))


def build_data() -> dict:
    template = (HERE / "template-v0.3.0.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(template, "html.parser")
    script = next(s.get_text() for s in soup.find_all("script") if "const pages=" in s.get_text())
    metadata = json.loads(re.search(r"const pages=(\[.*?\]);const home=", script, re.S).group(1))
    baseline = []
    for meta in metadata:
        article = soup.select_one(f'article[data-slug="{meta["slug"]}"]')
        baseline.append(page(meta["slug"], meta["title"], meta["group"], meta["summary"],
                             article.select_one(".prose").decode_contents()))
    data = {"latest": LATEST, "versions": {}}
    for version in VERSIONS:
        commit = git("rev-parse", f"v{version}^{{commit}}").strip()
        pages = []
        if version in {"0.3.0", LATEST}:
            for item in deepcopy(baseline):
                if version == "0.3.0" and item["slug"] == "sdk-telemetry":
                    continue  # This example was added after the 0.3.0 release tag.
                if version == LATEST:
                    for key in ("body", "summary"):
                        item[key] = item[key].replace("0.3.0", version)
                    item["body"] = item["body"].replace("(new in v0.4.0)", "(introduced in v0.3.0)")
                if item["slug"] != "reference":
                    pages.append(item)
        else:
            readme = tagged(version, "README.md")
            # Use pinned commands in an archive, never unpinned latest upgrades.
            readme = re.sub(r"python -m pip install (?:--upgrade )?energychain(?=\s|$)",
                            f"python -m pip install energychain=={version}", readme)
            pages.append(page("overview", "Introduction", "Start here", f"Published EnergyChain v{version} SDK.",
                              render_md(readme, version, commit)))
            install = (f"# Installation\n\nInstall the selected archived release with Python 3.10 or newer.\n\n```bash\n"
                       f"python -m pip install energychain=={version}\npython -m pip check\n```\n\n"
                       "The core uses only standard-library runtime dependencies. Model and document extras were introduced in v0.3.0 and are absent in this release.\n")
            pages.append(page("installation", "Installation", "Start here", "Install this exact release.", render_md(install, version, commit)))
            quick = "# Your first energy application\n\nThis example uses simulated energy data and needs no model credentials.\n\n```python\n" + tagged(version, "examples/quickstart.py") + "\n```\n"
            pages.append(page("quickstart", "Your first energy application", "Start here", "Run the release's offline quickstart.", render_md(quick, version, commit)))
            pages.append(from_doc(version, commit, "architecture", "System architecture", "Core concepts", "docs/architecture.md"))
            if version == "0.2.0":
                pages.append(from_doc(version, commit, "product-architecture", "Product architecture", "Core concepts", "docs/product-architecture-v01.md"))
                pages.append(from_doc(version, commit, "safety-actions", "Safety and authorization", "Operations", "docs/security.md"))
                pages.append(from_doc(version, commit, "release-notes", "Release notes", "Releases", "docs/release-notes-v0.2.0.md"))
            examples = "# Examples\n\nThese examples come from the selected release tag. Run them from its source checkout. External providers require your own authorized configuration.\n\n"
            for path in git("ls-tree", "-r", "--name-only", f"v{version}", "examples").splitlines():
                if path.endswith(".py"):
                    examples += f"## {Path(path).stem.replace('_', ' ').title()}\n\n```python\n{tagged(version,path)}\n```\n\n[Tagged source]({SOURCE}/blob/{commit}/{path}).\n\n"
            pages.append(page("examples", "Developer examples", "Guides", "Examples from this exact release.", render_md(examples, version, commit)))
        # Full source guides replace hand-maintained summaries for these APIs.
        if version in {"0.3.0", LATEST}:
            for slug, title, path in [
                ("model-gateway", "Model Gateway", "docs/model-gateway.md"),
                ("document-intelligence", "Document Intelligence", "docs/document-intelligence.md"),
                ("product-architecture", "Product architecture", "docs/product-architecture-v01.md"),
                ("safety-actions", "Safety and authorization", "docs/security.md"),
            ]:
                pages = [p for p in pages if p["slug"] != slug]
                pages.append(from_doc(version, commit, slug, title, "Intelligence", path))
            if version == LATEST:
                pages.append(from_doc(version, commit, "intelligence-runtime", "EnergyIntelligence", "Intelligence", "docs/intelligence-runtime.md"))
                pages.append(from_doc(version, commit, "upgrading", "Upgrade and migration", "Releases", "docs/upgrading.md"))
                pages = [p for p in pages if p["slug"] not in {"sdk-telemetry", "roadmap"}]
                pages.append(from_doc(version, commit, "sdk-telemetry", "SDK usage metrics (opt-in)", "Operations", "docs/telemetry-opt-in.md"))
                pages.append(from_doc(version, commit, "roadmap", "Release status and boundaries", "Releases", "docs/release-notes-v0.4.0.md"))
                for slug in ("overview", "agents", "workflows", "telemetry"):
                    p = next(p for p in pages if p["slug"] == slug)
                    p["body"] = ('<aside class="note"><strong>New in v0.4.0: EnergyIntelligence.</strong> '
                                 'Execute bounded plans with dependent tool outputs, evidence records, SQLite replay and trusted event subscriptions. '
                                 '<a href="/docs/0.4.0/intelligence-runtime/">Read the complete runtime guide →</a></aside>') + p["body"]
            else:
                pages.append(from_doc(version, commit, "release-notes", "Release notes", "Releases", "docs/release-notes-v0.3.0.md"))
        pages.append(page("reference", "API and module reference", "Operations", "Public exports and release-bound source reference.", render_md(api_reference(version, commit), version, commit)))
        pages.append(from_doc(version, commit, "releasing", "Publishing a release", "Releases", "docs/releasing.md"))
        pages.append(from_doc(LATEST, commit, "versions", "Documentation versions", "Releases", "docs/versions.md"))
        # Rewrite all internal navigation to the selected release; source links never target main.
        for p in pages:
            fragment = BeautifulSoup(p["body"], "html.parser")
            for link in fragment.find_all("a", href=True):
                href = link["href"]
                if href.startswith("/docs/"):
                    if re.match(r"/docs/0\.\d+\.\d+/", href):
                        continue
                    match = re.match(r"/docs/([^/#]*)(?:/)?(#[^ ]*)?$", href)
                    if match:
                        link["href"] = f"/docs/{version}/{match[1] or 'overview'}/" + (match[2] or "")
                elif href.startswith(SOURCE + "/blob/main/"):
                    link["href"] = href.replace("/blob/main/", f"/blob/{commit}/")
            p["body"] = str(fragment)
            p["search"] = fragment.get_text(" ", strip=True)
        # Stable navigation order independent of source-file order.
        order = ["overview", "installation", "quickstart", "learning-path", "intelligence-runtime", "architecture",
                 "product-architecture", "data-model", "connectors", "csv-data", "home-assistant", "solar-weather",
                 "tools", "memory", "agents", "model-gateway", "document-intelligence", "skills", "planning",
                 "fleets", "workflows", "telemetry", "safety-actions", "examples", "testing", "production",
                 "reference", "troubleshooting", "sdk-telemetry", "upgrading", "roadmap", "release-notes", "releasing", "versions"]
        pages.sort(key=lambda p: order.index(p["slug"]) if p["slug"] in order else 999)
        data["versions"][version] = {"commit": commit, "archived": version != LATEST, "pages": pages}
    return data


def build(output: Path) -> None:
    data = build_data()
    soup = BeautifulSoup((HERE / "template-v0.3.0.html").read_text(encoding="utf-8"), "html.parser")
    for script in list(soup.find_all("script")):
        if "const pages=" in script.get_text():
            script.decompose()
    soup.title.string = "EnergyChain Docs v0.4.0 — versioned Python SDK documentation"
    soup.select_one('meta[name="description"]')["content"] = "EnergyChain v0.4.0 documentation: EnergyIntelligence, models, documents, tools and release archives for v0.1.0–v0.4.0."
    for canonical in soup.select('link[rel="canonical"]'):
        canonical.decompose()
    canonical = soup.new_tag("link", rel="canonical", href="https://energychain.app/docs/0.4.0/overview/")
    canonical["id"] = "docs-canonical"
    soup.head.append(canonical)
    version = soup.select_one(".version")
    version.replace_with(BeautifulSoup('<label class="version-control" for="docs-version"><span>Version</span><select id="docs-version" aria-label="Documentation version">' + "".join(
        f'<option value="{v}">v{v} {"(latest)" if v == LATEST else "(archive)"}</option>' for v in VERSIONS) + '</select></label>', "html.parser"))
    sidebar = soup.select_one("#sidebar")
    for node in list(sidebar.select(".navgroup,.sidebar-bottom")):
        node.decompose()
    nav = soup.new_tag("nav", id="doc-nav")
    nav["aria-label"] = "Topics in the selected version"
    sidebar.append(nav)
    main = soup.select_one("#content")
    main.clear()
    # Useful current-version fallback for no-JavaScript readers and crawlers.
    first = data["versions"][LATEST]["pages"][0]
    main.append(BeautifulSoup('<article class="article"><h1>EnergyChain v0.4.0 documentation</h1><div class="prose">' + first["body"] + '</div></article><noscript><p>Enable JavaScript for version selection and search. <a href="' + SOURCE + '/tags">Tagged documentation source</a> is also available.</p></noscript>', "html.parser"))
    style = soup.new_tag("style")
    style.string = (HERE / "versioned.css").read_text(encoding="utf-8")
    soup.head.append(style)
    payload = soup.new_tag("script", id="docs-data", type="application/json")
    payload.string = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026")
    soup.body.append(payload)
    runtime = soup.new_tag("script")
    runtime.string = (HERE / "versioned.js").read_text(encoding="utf-8")
    soup.body.append(runtime)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(str(soup), encoding="utf-8")
    manifest = {"latest": LATEST, "versions": {v: {"commit": d["commit"], "topics": [p["slug"] for p in d["pages"]]} for v,d in data["versions"].items()}}
    output.with_name("versions.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "versions": {v: len(d["pages"]) for v,d in data["versions"].items()}, "bytes": output.stat().st_size}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
