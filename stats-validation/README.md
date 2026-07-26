# Statistical validation

Two independent implementations compute the same statistics from the same raw
CSV, and the comparison is published.

- **Path A** is Figura exactly as shipped: the real CSV parser, the real spec
  builders, and `render_figure()`.
- **Path B** is a Python implementation written from the prose spec in
  `spec/`, by an implementer who has not read `R/`.

Run everything:

    make -C stats-validation test all

Read `results/scorecard.html` in a browser. It is self-contained and opens
from `file://`.

**`all` exits non-zero whenever a case publishes findings, and that is the
designed outcome, not a broken run.** `logistic-dirty` exists to publish the
app-vs-exported-script divergence of `issues/02`, so it fails on purpose. The
scorecard is written BEFORE the failure is reported — a non-zero `all` means
"findings exist, go read them", never "nothing was published".

**`test` is green.** It was red by design for a while: Task A14's in-repo half
published the advisory-diagnostics contract — the specs, `INTERFACES.md`, the
harvester, the comparator and the case files — ahead of the clean-room
implementation, and `compare.py`'s `PENDING_PATH_B_DIAGNOSTICS` marked the
affected coverage **DEFERRED** on the scorecard so nothing claimed to have been
checked that was not. `validate/logistic.py` and `validate/cox.py` now return
their `diagnostics` blocks, `PENDING_PATH_B_DIAGNOSTICS` is empty, and every
suite passes. A red `test` is now a real failure.

## The webR tier — a hand-run release gate

Everything above runs **native R**. It proves the statistics are right; it says
nothing about the runtime the user actually gets, which is R compiled to
WebAssembly. wasm has no 80-bit extended precision (R's `long double`
accumulators fall back to double) and webR ships reference BLAS/LAPACK rather
than Accelerate, so an iterative fit — Cox's Newton-Raphson, logistic's IRLS —
is where a difference would show.

`stats-validation/e2e/webr-parity.spec.js` drives the **shipped UI** in a real
browser (upload, map roles, confirm the event value, set reference levels and
increments, render, read `#stats`) and compares the displayed table against the
native-R `text` in `results/<id>.figura.json`, cell by cell. It adds no test
hook to `web/`, and it lives here with its own Playwright config so `tests/`
and the repo-root `playwright.config.js` stay untouched.

Run it **from the repo root**:

    make -C stats-validation webr

or, equivalently and explicitly:

    rm -rf web/R && cp -R R web/R
    npx playwright test --config stats-validation/e2e/playwright.config.js

`npm run serve` (which the config starts on port 8321) serves `web/`, and
`web/R/` is a gitignored build copy of `R/` — refresh it first or the worker
fetches stale or missing R sources. `rm -rf` first is not optional: a bare
`cp -R R web/R` nests into an existing directory. Chromium may need
`npx playwright install chromium` once.

**It is excluded from CI, from `make all`, and from `make test`, deliberately.**
It needs a browser and the network (Playwright downloads the webR runtime and
its packages from the CDN), which is the slow/flaky combination the repo's
CLAUDE.md keeps out of CI. Run it before a release, then rebuild the scorecard
(`make -C stats-validation all`) to publish the result.

**Differences are recorded, not thrown.** A cell that disagrees with native R
becomes a `WEBR_DRIFT` entry in `results/webr-tier.json`, so a first run
produces a measured number rather than a red X of unknown size. Hard
preconditions — the page rendered, the table parsed, the row count matched —
*are* asserted, so a harness failure stays loud and never masquerades as "no
drift found". The spec deletes `results/webr-tier.json` before it runs: a run
that dies before writing publishes nothing rather than last release's numbers
under this release's date, and the scorecard's empty state says so.

Coverage is the two ratio-table cases with a full native-R display artifact,
`logistic-confounding` and `cox-adjusted`. The rest of the roster is Phase 2 —
it needs the shared-boot refactor of the existing suites.

On the scorecard, read the **Compared** column before drawing a conclusion
about a finding. "Figura" is the screen on the display tier and the harvest
from re-running the exported `.R` on the exact tier, and on the script tier the
"Python" column is the exported script rather than Path B. Every one of
`logistic-dirty`'s findings is an *exported script* row: the numbers on screen
were right.

**If you are implementing Path B: do not read `R/*.R`.** Independence is the
only thing this exercise measures. A port that reproduces the same misreading
of the spec proves nothing.

Phase 1 never edits `R/` or `web/` — this harness is entirely new code and
data living under `stats-validation/`. Harness JS tests are run via
`stats-validation`'s own `Makefile` targets, not the repo's `npm run
test:unit` chain; they are a separate test surface and must not be appended
to that hand-maintained chain.
