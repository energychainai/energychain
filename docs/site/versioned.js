"use strict";
(() => {
  const data = JSON.parse(document.getElementById("docs-data").textContent);
  const main = document.getElementById("content");
  const selector = document.getElementById("docs-version");
  const nav = document.getElementById("doc-nav");
  const sidebar = document.getElementById("sidebar");
  const search = document.getElementById("search");
  const results = document.getElementById("results");
  const toggle = document.getElementById("toggle");
  const toc = document.getElementById("toc");
  let selected = data.latest, current = "overview";
  const html = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const path = (version, slug) => `/docs/${version}/${slug}/`;
  function route() {
    const parts = location.pathname.replace(/^\/docs\/?/, "").split("/").filter(Boolean);
    const candidate = parts[0] || "";
    if (/^v?\d+\.\d+\.\d+$/.test(candidate)) {
      return {version:candidate.replace(/^v/, ""), slug:parts[1] || "overview"};
    }
    return {version:data.latest, slug:candidate === "index.html" ? "overview" : candidate || "overview"};
  }
  function closeNavigation() {
    sidebar.classList.remove("open"); toggle.setAttribute("aria-expanded", "false");
    search.value = ""; results.style.display = "none";
  }
  function render(version, slug, mode = "none", focus = false) {
    if (!Object.hasOwn(data.versions, version)) {
      selector.value = data.latest;
      main.innerHTML = `<article class="article"><h1>Documentation version unavailable</h1><div class="prose"><p>Version ${html(version)} is not one of the published documentation sets.</p><a href="${path(data.latest,"versions")}">Choose a published version</a></div></article>`;
      nav.innerHTML = ""; toc.innerHTML = "";
      document.title = "Documentation version unavailable — EnergyChain";
      return;
    }
    selected = version; current = slug;
    const release = data.versions[version], pages = release.pages;
    selector.value = version;
    const groups = [...new Set(pages.map(p => p.group))];
    nav.innerHTML = groups.map(group => `<div class="navgroup"><div class="navlabel">${html(group)}</div>${pages.filter(p => p.group === group).map(p => `<a class="doc-link${p.slug === slug ? " active" : ""}" data-slug="${p.slug}" href="${path(version,p.slug)}"${p.slug === slug ? ' aria-current="page"' : ""}>${html(p.title)}</a>`).join("")}</div>`).join("");
    const item = pages.find(p => p.slug === slug);
    const title = item ? item.title : "Topic unavailable in this version";
    let body;
    if (item) body = `<p class="lede">${html(item.summary)}</p><div class="prose">${item.body}</div>`;
    else {
      const available = Object.entries(data.versions).filter(([,r]) => r.pages.some(p => p.slug === slug));
      body = `<div class="prose missing-topic" role="status"><p>This topic is not included in v${html(version)}. No newer-version content is shown here.</p>${available.length ? `<p>Read this topic in: ${available.map(([v]) => `<a href="${path(v,slug)}">v${html(v)}</a>`).join(", ")}.</p>` : ""}<p><a href="${path(version,"overview")}">Open the v${html(version)} introduction →</a></p></div>`;
    }
    const archive = release.archived ? `<div class="version-banner"><strong>Archived documentation · v${html(version)}</strong>. Examples and API references match this release. <a href="${path(data.latest,slug)}">Read latest v${data.latest}</a>.</div>` : `<div class="version-banner">Latest published release · <strong>v${html(version)} alpha</strong> · Python 3.10+ · <a href="https://pypi.org/project/energychain/${version}/">PyPI release</a></div>`;
    main.innerHTML = `<article class="article" tabindex="-1" data-version="${version}" data-slug="${html(slug)}"><div class="breadcrumbs"><a href="${path(version,"overview")}">Docs</a><span>/</span><span>v${version}</span><span>/</span><span>${html(item?.group || "Version availability")}</span></div>${archive}<h1>${html(title)}</h1>${body}<div class="source-note">Source: <a href="https://github.com/energychainai/energychain/tree/${release.commit}">v${version} · ${release.commit.slice(0,7)}</a>. Release-specific examples and APIs; installation pins and navigation receive documentation corrections. <a href="${path(version,"versions")}">About versions</a>.</div></article>`;
    document.title = `${title} — EnergyChain v${version} Docs`;
    document.getElementById("docs-canonical").href = `https://energychain.app${path(version,slug)}`;
    for (const link of document.querySelectorAll(".topnav a[href^='/docs/']")) link.href = path(version,"quickstart");
    const headings = [...main.querySelectorAll("h2,h3")];
    const used = new Set();
    headings.forEach((heading,index) => {
      let id = heading.id || heading.textContent.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"") || `section-${index}`;
      if (used.has(id)) id += `-${index}`;
      used.add(id); heading.id = id;
    });
    toc.innerHTML = headings.map(h => `<a href="#${encodeURIComponent(h.id)}"${h.tagName === "H3" ? ' style="padding-left:12px"' : ""}>${html(h.textContent)}</a>`).join("");
    if (mode === "push") history.pushState({version,slug}, "", path(version,slug));
    if (mode === "replace") history.replaceState({version,slug}, "", path(version,slug) + location.hash);
    closeNavigation();
    if (focus) main.querySelector("article").focus({preventScroll:true});
    const anchor = decodeURIComponent(location.hash.slice(1));
    if (anchor && document.getElementById(anchor)) document.getElementById(anchor).scrollIntoView();
    else window.scrollTo({top:0,behavior:"instant"});
  }
  document.addEventListener("click", event => {
    const copy = event.target.closest("[data-copy]");
    if (copy) {
      navigator.clipboard.writeText(copy.closest(".codebox").querySelector("pre").textContent)
        .then(() => {copy.textContent="Copied ✓"; setTimeout(() => copy.textContent="Copy ↗",1500);})
        .catch(() => {copy.textContent="Select code to copy";});
      return;
    }
    const link = event.target.closest("a");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target === "_blank") return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith("/docs/")) return;
    if (url.pathname === location.pathname && url.hash) return;
    event.preventDefault(); history.pushState({}, "", url.pathname + url.hash);
    const target = route(); render(target.version,target.slug,"replace",true);
  });
  selector.addEventListener("change", () => render(selector.value,current,"push",true));
  toggle.addEventListener("click", () => toggle.setAttribute("aria-expanded",String(sidebar.classList.toggle("open"))));
  window.addEventListener("popstate", () => {const r = route();render(r.version,r.slug,"none");});
  search.addEventListener("input", () => {
    const query = search.value.trim().toLowerCase();
    if (!query) {results.style.display="none";return;}
    const hits = data.versions[selected].pages.filter(p => `${p.title} ${p.summary} ${p.search}`.toLowerCase().includes(query)).slice(0,12);
    results.innerHTML = hits.length ? hits.map(p => `<a class="result" href="${path(selected,p.slug)}">${html(p.title)}<small>v${selected} · ${html(p.group)}</small></a>`).join("") : `<div class="empty" role="status">No results in v${selected}. Select another version to search it.</div>`;
    results.style.display="block";
  });
  document.addEventListener("keydown",event => {
    if (event.key === "/" && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)) {event.preventDefault();search.focus();}
    if (event.key === "Escape") {search.blur();closeNavigation();}
  });
  const initial = route();render(initial.version,initial.slug,"replace");
})();
