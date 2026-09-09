// Writes each registered page's demo spec to scripts/pages/.build/<slug>.spec.json
// for render-examples.R. Run from the repo root.
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { PAGES } from "./registry.mjs";

const out = path.resolve("scripts/pages/.build");
await mkdir(out, { recursive: true });
for (const p of PAGES) {
  const spec = p.demoSpec();
  await writeFile(path.join(out, `${p.slug}.spec.json`), JSON.stringify(spec));
  console.log(`wrote .build/${p.slug}.spec.json (${p.key})`);
}
