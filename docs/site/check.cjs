const fs = require("node:fs");
const assert = require("node:assert/strict");
const { JSDOM, VirtualConsole } = require("jsdom");
const content = fs.readFileSync(process.argv[2], "utf8");
const failures = [], copied = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", error => failures.push(error.message));
const dom = new JSDOM(content, {
  url: "https://energychain.app/docs/", runScripts: "dangerously", virtualConsole,
  beforeParse(window) {
    window.scrollTo = () => {};
    window.HTMLElement.prototype.scrollIntoView = () => {};
    Object.defineProperty(window.navigator, "clipboard", {value:{writeText:async text => copied.push(text)}});
  }
});
const w = dom.window, d = w.document;
const dataset = JSON.parse(d.querySelector("#docs-data").textContent);
const select = version => {
  d.querySelector("#docs-version").value = version;
  d.querySelector("#docs-version").dispatchEvent(new w.Event("change", {bubbles:true}));
};
const go = path => {w.history.pushState({}, "", path);w.dispatchEvent(new w.PopStateEvent("popstate"));};
const input = term => {const field = d.querySelector("#search");field.value = term;field.dispatchEvent(new w.Event("input", {bubbles:true}));};
const tick = () => new Promise(resolve => setTimeout(resolve, 10));
(async () => {
  assert.equal(w.location.pathname,"/docs/0.4.0/overview/");
  assert.equal(d.querySelector("#docs-version").value,"0.4.0");
  assert.equal(d.querySelector("#docs-canonical").href,"https://energychain.app/docs/0.4.0/overview/");
  let rendered = 0;
  for (const [version,release] of Object.entries(dataset.versions)) {
    for (const page of release.pages) {
      go(`/docs/${version}/${page.slug}/`);
      assert.equal(d.querySelector("article h1").textContent,page.title);
      assert.equal(d.querySelector("article").dataset.version,version);
      assert.match(d.querySelector(".source-note").textContent,new RegExp(release.commit.slice(0,7)));
      assert.equal(d.querySelectorAll('[aria-current="page"]').length,1);
      const ids = [...d.querySelectorAll("[id]")].map(x => x.id);
      assert.equal(ids.length,new Set(ids).size,`duplicate ID on ${version}/${page.slug}`);
      for (const link of d.querySelectorAll("#doc-nav a")) assert.ok(link.pathname.startsWith(`/docs/${version}/`));
      if (release.archived) {
        for (const code of d.querySelectorAll("main pre code")) {
          assert.doesNotMatch(code.textContent, /python -m pip install (?:--upgrade )?energychain(?=\s|$)/,
            `unpinned archived install on ${version}/${page.slug}`);
        }
      }
      rendered++;
    }
  }
  go("/docs/0.4.0/installation/");select("0.2.0");
  assert.equal(w.location.pathname,"/docs/0.2.0/installation/");
  assert.match(d.querySelector("article").textContent,/energychain==0\.2\.0/);
  assert.match(d.querySelector(".version-banner").textContent,/Archived/);
  go("/docs/0.4.0/intelligence-runtime/");select("0.3.0");
  assert.equal(w.location.pathname,"/docs/0.3.0/intelligence-runtime/");
  assert.match(d.querySelector("h1").textContent,/unavailable/i);
  assert.match(d.querySelector(".missing-topic").textContent,/not included in v0\.3\.0/);
  assert.equal(d.querySelectorAll(".prose .codebox").length,0);
  assert.ok(d.querySelector('.missing-topic a[href="/docs/0.4.0/intelligence-runtime/"]'));
  select("0.4.0");
  assert.match(d.querySelector("h1").textContent,/EnergyIntelligence/);
  go("/docs/0.1.0/installation/");input("ModelGateway");
  assert.match(d.querySelector("#results").textContent,/No results in v0\.1\.0/);
  select("0.4.0");input("OutputRef");
  assert.ok(d.querySelectorAll("#results a").length>0);
  for (const link of d.querySelectorAll("#results a")) assert.ok(link.pathname.startsWith("/docs/0.4.0/"));
  go("/docs/quickstart/");
  assert.equal(d.querySelector("article").dataset.version,"0.4.0");
  assert.equal(d.querySelector("article").dataset.slug,"quickstart");
  go("/docs/0.3.0/model-gateway/");
  assert.match(d.querySelector("article").textContent,/energychain\[models\]==0\.3\.0/);
  select("0.4.0");
  assert.match(d.querySelector("article").textContent,/energychain\[models\]==0\.4\.0/);
  w.history.back();await tick();
  assert.equal(d.querySelector("#docs-version").value,"0.3.0");
  w.history.forward();await tick();
  assert.equal(d.querySelector("#docs-version").value,"0.4.0");
  d.querySelector("[data-copy]").click();await tick();
  assert.ok(copied[0].includes("energychain[models]==0.4.0"));
  d.querySelector("#toggle").click();
  assert.equal(d.querySelector("#toggle").getAttribute("aria-expanded"),"true");
  d.dispatchEvent(new w.KeyboardEvent("keydown", {key:"Escape",bubbles:true}));
  assert.equal(d.querySelector("#toggle").getAttribute("aria-expanded"),"false");
  d.activeElement.blur();
  d.dispatchEvent(new w.KeyboardEvent("keydown", {key:"/",bubbles:true}));
  assert.equal(d.activeElement.id,"search");
  go("/docs/9.9.9/overview/");
  assert.match(d.querySelector("h1").textContent,/version unavailable/i);
  assert.deepEqual(failures,[]);
  console.log(JSON.stringify({rendered_topics:rendered,versions:Object.keys(dataset.versions),
    checks:["direct routes","source commits","pinned installs","scoped navigation and search","missing-version/topic states","version retention","legacy links","back/forward","clipboard","keyboard and mobile menu semantics","unique IDs","no runtime errors"],result:"passed"},null,2));
  dom.window.close();
})().catch(error => {console.error(error);dom.window.close();process.exitCode=1;});
