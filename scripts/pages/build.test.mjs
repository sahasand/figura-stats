import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
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

// 2b. Orphan check: the freshness loop above is one-way — it only ever visits
// the paths build() itself still produces, so a page whose registry entry was
// REMOVED (its directory and index.html left committed on disk) would stay
// published forever and nothing above would notice. Walk web/ the other way:
// every top-level directory that isn't part of the app shell (fonts, guided,
// lib, R, webr) and carries a committed index.html must be exactly the
// index.html/sitemap.xml/robots.txt set build() produces — no more, no less.
const NOT_GENERATED_DIRS = new Set(["fonts", "guided", "lib", "R", "webr"]);
const topLevel = await readdir(webDir, { withFileTypes: true });
const committedGenerated = [];
for (const entry of topLevel) {
  if (!entry.isDirectory() || NOT_GENERATED_DIRS.has(entry.name)) continue;
  const siblings = await readdir(path.join(webDir, entry.name));
  if (siblings.includes("index.html")) committedGenerated.push(`${entry.name}/index.html`);
}
committedGenerated.push("sitemap.xml", "robots.txt");
const builtGenerated = [...built.keys()].filter(
  (k) => k.endsWith("/index.html") || k === "sitemap.xml" || k === "robots.txt");
assert.deepEqual(
  committedGenerated.sort(), builtGenerated.sort(),
  "web/ has a committed generated page that build() no longer produces (or vice versa) " +
  "— an orphaned page from a removed registry entry would otherwise stay published",
);

// 3. Structure of every analysis page.
const expectedUrls = new Set([`${SITE}/`, `${SITE}/validation.html`, `${SITE}/about/`, `${SITE}/sample-size/`,
  ...PAGES.map((p) => `${SITE}/${p.slug}/`)]);
for (const p of PAGES) {
  const html = built.get(`${p.slug}/index.html`);
  assert.ok(html, `${p.slug}/index.html built`);
  assert.equal((html.match(/<h1[\s>]/g) || []).length, 1, `${p.slug}: exactly one <h1>`);
  assert.ok(html.includes(`<title>${p.title} — Figura</title>`), `${p.slug}: title`);
  assert.ok(html.includes(`<meta name="description" content="`), `${p.slug}: description`);
  assert.ok(html.includes(`href="../#${p.key}/example"`), `${p.slug}: example button`);
  assert.ok(html.includes(`href="../#${p.key}/analyze"`), `${p.slug}: analyze button`);
  assert.ok(html.includes("Analyses were performed with Figura"), `${p.slug}: citation`);
  for (const s of p.sections)
    assert.ok(html.includes(`<h2>${s.title}</h2>`), `${p.slug}: section "${s.title}"`);
  // Code output is never labelled as methods text.
  const labelledAsMethods = html.includes("ready to paste into a methods section");
  assert.equal(labelledAsMethods, p.textKind !== "code", `${p.slug}: example text label matches its kind`);
  // The example caption names what the render actually is.
  const isTable = /<table[\s>]/.test(JSON.parse(await readFile(path.join(webDir, p.slug, "example.json"), "utf8")).svg);
  assert.ok(html.includes(isTable ? "the table Figura renders" : "the figure Figura renders"), `${p.slug}: example caption`);
  assert.ok(!html.includes(isTable ? "the figure Figura renders" : "the table Figura renders"), `${p.slug}: example caption is not the other kind`);
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
assert.deepEqual(new Set(locs), expectedUrls, "sitemap lists exactly the ten URLs");
assert.equal(locs.length, 10);
assert.ok(built.get("robots.txt").includes(`Sitemap: ${SITE}/sitemap.xml`));
console.log("build.test.mjs OK");
