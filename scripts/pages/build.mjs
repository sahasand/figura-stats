// scripts/pages/build.mjs — generates the crawlable pages into web/.
//   npm run build:pages
// Deterministic: same inputs, byte-identical output (build.test.mjs pins it).
// Inputs: registry.mjs (copy + imported UNDERSTAND_SECTIONS + demo data) and
// the committed web/<slug>/example.json renders (npm run build:examples).
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderPlannerPage } from "./planner.mjs";
import { PAGES, SITE } from "./registry.mjs";
import { toCsv } from "../../web/lib/csv.js";
import { renderAnalysisPage, renderAboutPage, renderSitemap, renderRobots } from "./html.mjs";

export async function buildAll({ webDir }) {
  const out = new Map();
  const navFor = (currentSlug) => [
    { href: "../", label: "App" },
    ...PAGES.map((p) => ({ href: `../${p.slug}/`, label: p.title, slug: p.slug,
                           current: p.slug === currentSlug })),
    { href: "../sample-size/", label: "Sample size & power" },
    { href: "../about/", label: "About", current: currentSlug === "about" },
    { href: "../validation.html", label: "Validation" },
  ];
  for (const p of PAGES) {
    const example = JSON.parse(
      await readFile(path.join(webDir, p.slug, "example.json"), "utf8"));
    out.set(`${p.slug}/index.html`, renderAnalysisPage(p, example, navFor(p.slug)));
    out.set(`${p.slug}/sample.csv`, toCsv(p.demo.rows, p.demo.columns));
  }
  out.set("about/index.html", renderAboutPage(navFor("about")));
  out.set("sample-size/index.html", renderPlannerPage(await readFile(path.join(webDir, "index.html"), "utf8")));
  out.set("sitemap.xml", renderSitemap([
    `${SITE}/`, `${SITE}/validation.html`, `${SITE}/about/`, `${SITE}/sample-size/`,
    ...PAGES.map((p) => `${SITE}/${p.slug}/`)]));
  out.set("robots.txt", renderRobots());
  return out;
}

export async function main() {
  const webDir = path.resolve("web");
  const built = await buildAll({ webDir });
  for (const [rel, content] of built) {
    const target = path.join(webDir, rel);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content);
    console.log(`wrote web/${rel}`);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}
