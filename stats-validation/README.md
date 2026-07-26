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

## The findings baseline, and how CI uses it

`make all` exiting non-zero is the designed outcome, which leaves CI with a
problem: it can neither obey that exit code (permanently red, so everyone learns
to ignore the job, and the day a real regression lands nobody looks) nor discard
it (a job that ignores the exit code cannot catch a regression, which is the
only thing a gate is for). The answer is a tracked baseline of the findings we
have already read and accepted:

    make -C stats-validation gate           # check
    make -C stats-validation gate-update    # rewrite the baseline

`expected-findings.json` records every accepted finding by its **identity**
(case + code + term + quantity) and its **kind** (disposition, source, note),
plus each case's coverage counts and the run totals. `gate` passes when the
findings set matches exactly and fails when anything is **added, removed, or
changed in kind**, printing a readable baseline-vs-actual diff. Full argument in
`gate.py`'s module docstring.

Three properties are deliberate:

- **Measured values are not in the baseline.** `figura` and `python` are floats
  and float-derived display strings; a last-digit move in an odds ratio is not a
  regression and must never turn the build red. A finding *appearing* or
  *disappearing* is.
- **Order is not in the baseline.** Cases sort by id, findings by identity, so
  reshuffling `findings.json` is not a difference.
- **Coverage is in the baseline.** A case that silently stopped comparing
  anything would add no finding and remove none, so a findings-only gate would
  wave it through. `compared`, `passed`, `targets_met`, `targets` and
  `deferred_targets` are checked too — including coverage going *up*.

**A removed finding is a failure, not a celebration.** It means the evidence
moved and the baseline is now a stale description of the repo. That is exactly
what will happen when the Phase-2 export-path fix lands, and that fix's own PR
is where the baseline gets updated — **in the same commit as the change that
moved the evidence, reviewed alongside it, never as a drive-by.** The remedy is
printed by the failure itself, and repeated in a `_note` inside the file.

CI (`.github/workflows/ci.yml`, job `validation`) runs, in order: `make test`;
`make clean all` with its status recorded but not obeyed; `make gate` (the
actual verdict); a **freshness gate** — `git diff --exit-code` over
`results/findings.json` and `results/scorecard.html`, so a stale committed
artifact fails the build; and an upload of the scorecard. `webr-tier.json` is
excluded from the freshness diff — nothing in CI regenerates it, because the
webR tier is hand-run — but it is still uploaded. A missing `findings.json` is
a hard gate failure (exit 2), which is what catches a pipeline that died before
the comparator wrote anything: the one real risk of not obeying `all`'s status.

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
and the repo-root `playwright.config.js` stay untouched. The comparator itself
(`compareText`) and its cell-kind classification live in the sibling
`e2e/compare-text.mjs` — a plain-Node module, exported specifically so it can
be pinned by a plain node test (`e2e/compare-text.test.mjs`) that `make -C
stats-validation test` runs on every build, even though the Playwright spec
that is its only other caller stays excluded from CI. Before that split,
`compareText` had no test anywhere reachable from CI; an edit that made the
comparison always report "identical" would have failed nothing.

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
produces a measured number rather than a red X of unknown size.

**Not every compared cell is a number.** "N cells compared" sounds like N
measurements, but most of a rendered ratio table is static text: column
headers, row/term labels (including ones that look numeric, like the level
name "II" or "III"), and the deliberately-blank unadj/adj cells a categorical
covariate's own reference-level row carries. `webr-tier.json` publishes a
breakdown — top-level `cells_compared`, `cells_with_numbers`, and a
`cells_note` explaining the split (e.g. `36 = 12 numeric value cells + 7
methods sentences (5 containing a number) + 9 term labels + 2 header lines + 6
empty-vs-empty placeholder cells` — only the numeric-bearing cells can ever
show wasm-vs-native drift) — and the scorecard renders the honest phrasing:
"compared every one of the N strings the app displays … M of them carrying a
number." Per-case entries also carry `cell_kinds` and `cells_with_numbers` for
the same reason. This breakdown is derived from the same `compareText` call
that does the real comparison (not a second, independent classifier), so it
can never disagree with what was actually compared.

**Hard preconditions — the page rendered, the table parsed, the row count
matched — are asserted**, so a harness failure stays loud and never masquerades
as "no drift found". Unlike a value difference, a precondition failure (a
"structural drift", e.g. the two runtimes disagreeing on the row count) does
NOT stop the file from being written: it is caught per-case and published as
an honest `{id, aborted: true, reason}` case entry — the scorecard renders it
as its own ABORTED verdict, distinct from both IDENTICAL and DRIFT — and the
Playwright test still fails loudly afterward, so a partial/aborted run can
never be mistaken for a passing one. Before this, a precondition failure
aborted the whole spec before anything was written, so the single most
alarming class of drift rendered identically to "never run".

The spec deletes `results/webr-tier.json` before it runs: a run that dies
*before writing anything at all* (e.g. it crashes before the per-case loop even
starts) publishes nothing rather than last release's numbers under this
release's date, and the scorecard's empty state says so.

**The evidence is bound to the code it measured.** `webr-tier.json` also
records `commit` (the repo `HEAD` at run time, written ONLY by a real run of
`e2e/webr-parity.spec.js` — see that file's `repoCommit()` for the invariant
and the regression that once broke it) and `native_digest` (a sha256 of the
native `text` strings — from `results/<id>.figura.json` — that were actually
compared against). A later `make all` that changes native output changes the
digest, so previously-published webR evidence becomes visibly stale instead of
silently continuing to claim parity with numbers that no longer exist. The
scorecard shows the commit (short form) next to the runtime line, and — since
binding is only useful if staleness is actually visible, not just theoretically
detectable — it recomputes the digest from the artifacts on disk and says so on
the page when the two disagree, rather than requiring a reader to check by hand.

**That note is derived from the artifacts, never from live `git`, and the
distinction is load-bearing.** It used to compare `commit` against
`git rev-parse HEAD`, which broke in two ways. It could not survive its own
commit — publishing the scorecard advances `HEAD`, so the tracked file
permanently named the *previous* commit and could never again match a rebuild,
which makes the CI freshness gate below impossible. And it was *defeated* by the
one regression it was written for: a patch script that clobbers `commit` with
the current `HEAD` makes the two agree, so no note renders. `native_digest`
has neither problem — clobbering `commit` does not touch it, and the same
inputs always render the same HTML. What was given up is "`HEAD` has moved at
all", which fired on literally every commit and was noise. `build_scorecard.py`
now reads no live state whatsoever; `test_scorecard_is_a_pure_function_of_its_inputs`
pins that.

Coverage is the two ratio-table cases with a full native-R display artifact,
`logistic-confounding` and `cox-adjusted`. The rest of the roster is Phase 2 —
it needs the shared-boot refactor of the existing suites.

**The scorecard's headline tiles (values compared / differences / defects /
cases meeting targets) come from `findings.json` only.** A webR drift or
aborted row changes the WebR tier section, never those tiles — they are
`compare.py`'s native-R-vs-Python verdict, a separate comparison the webR tier
does not feed into. Read the WebR tier section itself for wasm-vs-native
parity.

`compareText` relies on `parseRatioTable`'s (`harness/parse-cells.mjs`) trim
asymmetry: `unadj`/`adj` cells are trimmed and default to `""` when missing,
but `term` is left exactly as split from the tab. A stray whitespace
difference on a `term` cell would therefore show up as a genuine `WEBR_DRIFT`
finding, while the same whitespace on a value cell would already have been
normalized away before the comparator ever saw it. See the comment on
`classifyColumn` in `e2e/compare-text.mjs` for where this matters.

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
