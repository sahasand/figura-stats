// stats-validation/e2e/playwright.config.js
//
// The webR release-gate tier's OWN Playwright config. It is deliberately not
// the repo-root playwright.config.js and this directory is deliberately not
// tests/e2e/: the root config and the app's own e2e suite are untouched by the
// validation harness (A17), so `npm run test:e2e` keeps meaning exactly what it
// meant before. Nothing discovers this config automatically — it runs only when
// named:
//
//     rm -rf web/R && cp -R R web/R          # web/R is a gitignored build copy
//     npx playwright test --config stats-validation/e2e/playwright.config.js
//
// (or `make -C stats-validation webr`, which does both steps). Both commands
// run from the REPO ROOT.
const path = require("path");

// The repo root: stats-validation/e2e -> stats-validation -> <root>.
const REPO_ROOT = path.join(__dirname, "..", "..");

module.exports = {
  testDir: __dirname,
  // ONE test drives BOTH cases through ONE page, deliberately: a page reload
  // throws away the Web Worker and therefore the booted webR runtime, so a
  // per-case test would re-download the runtime and every package each time.
  // The budget must therefore cover the whole chain — engine boot, the shared
  // package set, the lazy `survival` install for Cox, and two real fits — not
  // one fit. The root config's 240s covers a single-fit test; this is 20
  // minutes for the lot, and it is a ceiling, not an expectation.
  timeout: 1200000,
  workers: 1,
  fullyParallel: false,
  // A release gate is read by a human at the terminal; `list` prints each step.
  reporter: "list",
  // Same pattern as the root config. `cwd` is set explicitly because
  // Playwright defaults it to the CONFIG's directory — from here `npm run
  // serve` would resolve `--directory web` against stats-validation/e2e/ and
  // serve nothing.
  webServer: {
    command: "npm run serve",
    cwd: REPO_ROOT,
    url: "http://localhost:8321",
    reuseExistingServer: true,
    timeout: 240000
  },
  use: { baseURL: "http://localhost:8321" }
};
