import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { buildAll } from "./build.mjs";
import { PAGES, SITE } from "./registry.mjs";
import { parseCsv } from "../../web/lib/csv.js";

const webDir = path.resolve("web");
const built = await buildAll({ webDir });

// 1. Registry ↔ rail parity: every analysis the app offers has a page, and
//    no page names an analysis the app does not offer.
const indexHtml = await readFile(path.join(webDir, "index.html"), "utf8");
const railKeys = [...indexHtml.matchAll(/data-figure="(\w+)"/g)].map((m) => m[1]).sort();
assert.deepEqual(PAGES.map((p) => p.key).sort(), railKeys, "registry keys == rail buttons");

// 2. Freshness: what this commit builds is what is committed.
for (const [rel, content] of built) {
  const committed = await readFile(path.join(webDir, rel), "utf8");
  assert.equal(committed, content,
    `${rel} is stale — run \`npm run build:pages\` and commit the result`);
}

// 3. Structure of every analysis page.
const expectedUrls = new Set([`${SITE}/`, `${SITE}/validation.html`, `${SITE}/about/`,
  ...PAGES.map((p) => `${SITE}/${p.slug}/`)]);
for (const p of PAGES) {
  const html = built.get(`${p.slug}/index.html`);
  assert.ok(html, `${p.slug}/index.html built`);
  assert.equal((html.match(/<h1[\s>]/g) || []).length, 1, `${p.slug}: exactly one <h1>`);
  assert.ok(html.includes(`<title>${p.title} — Figura</title>`), `${p.slug}: title`);
  assert.ok(html.includes(`<meta name="description" content="`), `${p.slug}: description`);
  assert.ok(html.includes(`<link rel="canonical" href="${SITE}/${p.slug}/">`), `${p.slug}: canonical`);
  assert.ok(html.includes(`href="../#${p.key}/example"`), `${p.slug}: example button`);
  assert.ok(html.includes(`href="../#${p.key}/analyze"`), `${p.slug}: analyze button`);
  assert.ok(html.includes("Analyses were performed with Figura"), `${p.slug}: citation`);
  for (const s of p.sections)
    assert.ok(html.includes(`<h2>${s.title}</h2>`), `${p.slug}: section "${s.title}"`);
  // Code output is never labelled as methods text.
  const labelledAsMethods = html.includes("ready to paste into a methods section");
  assert.equal(labelledAsMethods, p.textKind !== "code", `${p.slug}: example text label matches its kind`);
  // No off-origin FETCHED resource: stylesheets, scripts, images. Plain links
  // (canonical, og:url, nav) are allowed to be absolute — they are not fetched.
  const fetched = [
    ...html.matchAll(/<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"/g),
    ...html.matchAll(/<script[^>]*src="([^"]+)"/g),
    ...html.matchAll(/<img[^>]*src="([^"]+)"/g),
  ].map((m) => m[1]);
  for (const url of fetched) {
    const origin = /^(https?:)?\/\//.test(url) ? new URL(url, SITE).origin : SITE;
    assert.equal(origin, SITE, `${p.slug}: off-origin resource ${url}`);
  }
  assert.ok(html.includes(`<link rel="canonical" href="${SITE}/${p.slug}/">`));
  // Sample CSV round-trips through the app's own parser.
  const csv = built.get(`${p.slug}/sample.csv`);
  const table = parseCsv(csv);
  assert.deepEqual(table.columns, p.demo.columns, `${p.slug}: sample.csv columns`);
  assert.equal(table.rows.length, p.demo.rows.length, `${p.slug}: sample.csv rows`);
}

// 4. About, sitemap, robots.
const about = built.get("about/index.html");
assert.ok(about.includes("Web Analytics"), "About discloses the Cloudflare beacon");
assert.ok(about.includes("/cdn-cgi/rum"), "About names the beacon path");
assert.ok(about.includes("@misc{figura2026"), "About carries BibTeX");
const sitemap = built.get("sitemap.xml");
const locs = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
assert.deepEqual(new Set(locs), expectedUrls, "sitemap lists exactly the nine URLs");
assert.equal(locs.length, 9);
assert.ok(built.get("robots.txt").includes(`Sitemap: ${SITE}/sitemap.xml`));
console.log("build.test.mjs OK");
