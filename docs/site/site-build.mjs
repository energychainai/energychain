import {spawnSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';

if(!process.argv.includes('--docs-only')) {
  for(const file of ['build-v03.mjs','integrate-popup.mjs','integrate-engagement.mjs']) {
    const result=spawnSync(process.execPath,[file],{stdio:'inherit'});
    if(result.error || result.status!==0) throw new Error('Existing website build failed: '+file);
  }
}
const document=gunzipSync(readFileSync('docs-versioned.html.gz')).toString('utf8');
const payload=document.match(/<script[^>]+id="docs-data"[^>]*>([\s\S]*?)<\/script>/);
if(!payload) throw new Error('Versioned documentation payload missing');
const data=JSON.parse(payload[1]);
const html=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const topics=[...new Set(Object.values(data.versions).flatMap(release=>release.pages.map(page=>page.slug)))];
let count=0;
function writePage(version,slug,directory) {
  const release=data.versions[version],page=release.pages.find(p=>p.slug===slug);
  const title=page?.title||'Topic unavailable in this version';
  const banner=release.archived?`Archived documentation · v${version}`:`Latest published release · v${version} alpha`;
  const body=page?`<p class="lede">${html(page.summary)}</p><div class="prose">${page.body}</div>`:
    `<div class="prose missing-topic"><p>This topic is not included in v${version}.</p><p><a href="/docs/${version}/overview/">Open the v${version} introduction</a></p><p><a href="/docs/${data.latest}/${slug}/">Read the latest version of this topic</a></p></div>`;
  const article=`<article class="article" data-version="${version}" data-slug="${slug}"><div class="version-banner">${banner}</div><h1>${html(title)}</h1>${body}<div class="source-note">Source: <a href="https://github.com/energychainai/energychain/tree/${release.commit}">v${version} · ${release.commit.slice(0,7)}</a>. <a href="/docs/${version}/versions/">Documentation versions</a>.</div></article>`;
  let output=document.replace(/<main\b[^>]*>[\s\S]*?<\/main>/,`<main class="content" id="content">${article}</main>`)
    .replace(/<title>[\s\S]*?<\/title>/,`<title>${html(title)} — EnergyChain v${version} Docs</title>`)
    .replace(/<link[^>]+id="docs-canonical"[^>]*>/,`<link rel="canonical" id="docs-canonical" href="https://energychain.app/docs/${version}/${slug}/">`);
  output=output.replace(/<option value="([^"]+)"[^>]*>/g,(_,value)=>`<option value="${value}"${value===version?' selected':''}>`);
  mkdirSync(directory,{recursive:true});
  writeFileSync(directory+'/index.html',output);
  count++;
}
mkdirSync('docs',{recursive:true});
writeFileSync('docs/index.html',document);
for(const version of Object.keys(data.versions)) {
  writePage(version,'overview',`docs/${version}`);
  for(const slug of topics) writePage(version,slug,`docs/${version}/${slug}`);
}
for(const slug of topics) {
  const destination=`/docs/${data.latest}/${slug}/`;
  const redirect=`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=${destination}"><link rel="canonical" href="https://energychain.app${destination}"><title>EnergyChain v${data.latest} documentation</title></head><body><a href="${destination}">Continue to the current documentation</a><script>location.replace(${JSON.stringify(destination)}+location.search+location.hash);</script></body></html>`;
  mkdirSync(`docs/${slug}`,{recursive:true});
  writeFileSync(`docs/${slug}/index.html`,redirect);
}
if(!process.argv.includes('--docs-only')) {
  const config=JSON.parse(readFileSync('vercel-docs-v04.json','utf8'));
  writeFileSync('vercel.json',JSON.stringify(config,null,2));
}
console.log(`EnergyChain docs v${data.latest}: ${count} static version/topic entry pages; archives ${Object.keys(data.versions).join(' / ')}`);
