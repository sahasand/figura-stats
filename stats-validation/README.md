# Statistical validation

Two implementations compute the same statistics from the same raw CSV, and the
comparison is published.

- **Path A** is Figura exactly as shipped: the real CSV parser, the real spec
  builders, and `render_figure()`.
- **Path B** is a second, Python implementation of the same analyses.

**What was actually done, stated precisely.** One specification — the prose in
`spec/` — was **transcribed from the R sources by an agent with full source
access**. That specification was then **implemented a second time in Python by
agents that never read `R/`**, against an acceptance suite whose expected values
were **computed in R**. It is a re-implementation from a written spec, not two
blind implementations from a shared problem statement.

That catches implementation bugs, library-default mismatches, and arithmetic
errors — the failure modes where a second author writing independent code from
a written rule lands somewhere different. It **cannot** catch a misreading baked
into the spec itself: if the spec transcribed R's behaviour wrongly, both paths
reproduce the same wrong thing and agree. Read
[How the clean room actually worked, and its limits](#how-the-clean-room-actually-worked-and-its-limits)
before quoting the agreement as evidence of anything wider.

Run everything:

    make -C stats-validation test all

Read `results/scorecard.html` in a browser. It is self-contained and opens
from `file://`.

**`all` exits non-zero whenever a case publishes findings, and that is the
designed outcome, not a broken run.** `logistic-dirty` exists to publish the
app-vs-exported-script divergence of `issues/02`, so it fails on purpose. The
scorecard is written BEFORE the failure is reported — a non-zero `all` means
"findings exist, go read them", never "nothing was published".

## How Path B was produced

The protocol, concretely enough to audit. Every Path B module was written by a
**separate agent dispatched with `claude -p` (never the in-session Agent tool,
which would have inherited this session's context) into a scratch directory
outside this repository** — not a branch, not a worktree, not a subdirectory
with a "do not look" instruction.

- **The scratch directory sat outside the repo tree**, so `R/`, `web/`,
  `cases/`, `results/`, this README, the repo's `CLAUDE.md`, the plan document
  and every other module's Python were not reachable by any path, glob, or
  `git` command available to that agent.
- **The bundle it received was:** `spec/<case>.md` (the prose specification for
  that case), `python/INTERFACES.md` (call signatures and return shapes),
  `requirements.txt`, an empty Python skeleton, and the acceptance suite
  `tests/test_<module>.py`. Nothing else. No repo context file, no
  project instructions, no sibling module.
- **No `R/` in any form** — not the sources, not a diff, not a quoted excerpt
  beyond what the spec itself states in prose.
- **The finished module was copied back** into `python/validate/` and committed
  here, together with the agent's own **`DECISIONS-<module>.md`** — one per
  module (`DECISIONS-{cox,km,logistic,groupcompare,summary,diagnostics}.md`),
  written in the scratch directory, recording every ambiguity the agent hit and
  how it resolved it. Those files are the audit trail: they are what an
  implementer with source access could not have written, and they are why the
  two leak episodes below are visible at all.
- The specs themselves were transcribed **into** `spec/` by a different agent
  that did have `R/` open. That direction of information flow is the whole
  design, and it is also the limit — see the next section.

The dispatch protocol is amendment A1 of
`docs/superpowers/plans/2026-07-25-statistical-validation.md`, which is tracked
in this repository. The per-task briefs and reports lived in
`stats-validation/.sdd/`, which is gitignored scratch and does not merge; the
protocol is recorded here so it survives without them.

## How the clean room actually worked, and its limits

This section exists because the shorter claim — "written from the prose spec by
an implementer who has not read `R/`" — was true about `R/` and misleading about
everything else. What follows is the whole of it.

**The no-`R/` half is real and verified.** No Path B agent read the R sources.

**But the bundle carried more than prose.** Two of its contents are not neutral:

- **`python/INTERFACES.md` names Path A internals and pre-resolves several
  points an independent implementer would plausibly have diverged on.** It
  pins the app's continuous-vs-categorical classification rule ("more than five
  distinct non-missing values"); it names R's "minmin" median rule for
  Kaplan-Meier by name and warns off the naive reading of the same formula; it
  states that Tukey and Dunn pair names run in *opposite* orders and says not to
  normalise them; it states that Fisher's exact test has no `statistic` at all
  because R's htest carries none; and it restates `fmt_num` as R's `signif`
  algorithm — scale, round half-to-even, unscale — **with the worked outputs**
  (`2.225 -> "2.22"`, `1.315 -> "1.32"`). Each of those is a real place a
  second implementation could have landed somewhere else, and each was handed
  over pre-decided.
- **The acceptance suites carry expected values computed in R, at 17
  significant digits.** An agent that could not derive a quantity could, in
  principle, fit the constant rather than the rule. (The suites are in the
  repository and readable; nothing about this is hidden.)

**Two episodes are disclosed by commit hash rather than argued away.**

- **`6d3ac38` relocated a leak instead of removing it.** Its stated purpose
  included "INTERFACES.md's precision note stripped of library names/kwargs" —
  and it did strip lifelines' name and the literal
  `fit_options={"precision": 1e-11, "r_precision": 1e-13}` from
  `INTERFACES.md`. In **the same commit** it added those same values, plus
  `"max_steps": 1000`, to `python/tests/test_cox.py`'s comment block, which the
  clean-room bundle also contained. The sanitization moved the information from
  one bundled file to another. `python/DECISIONS-cox.md` then cites
  `INTERFACES.md`'s numerical-precision note as the source of values that file
  no longer contained.
- **`e8405fc` retuned `_FIT_OPTIONS` against a residual measured relative to
  R.** It moved `validate/cox.py`'s solver settings from
  `precision=1e-11, r_precision=1e-13, max_steps=1000` to
  `precision=1e-15, r_precision=1e-17, max_steps=5000`, and the justification
  recorded in the code and in `DECISIONS-diagnostics.md` is the
  proportional-hazards global-p residual **"4.0e-8 -> 2.9e-13 relative to R"**.
  Tightening a convergence tolerance does not change which statistic is
  computed — but the target was R's answer, so this is a tuning step against the
  reference, and it belongs in the disclosure.

**The conclusion.** What this harness is: **one specification, transcribed from
the R sources by an agent with source access, implemented a second time in
Python by agents that never read the R, against an acceptance suite whose
expected values were computed in R.** Agreement between the two paths is strong
evidence against implementation bugs, library-default mismatches, and arithmetic
errors — the numerous, ordinary, expensive failures. It is **not** evidence
against a misreading baked into the specification: a spec that describes R
wrongly produces two implementations that agree with each other and with the
spec, and the comparison stays green. The specs are in `spec/`, they cite `R/`
line by line, and they are the artifact to attack if you want to attack this.

## Where the issue files live

The two real app-bug issues found by this work are at
**`stats-validation/issues/`** — `01-cox-blank-status-censored.md` and
`02-app-vs-exported-script-missing-values.md`.

That is a **deliberate deviation** from the convention in
`docs/agents/issue-tracker.md` and the repo `CLAUDE.md`, which put issues at
`.scratch/<slug>/issues/`. The reason is the Phase-1 constraint: `.scratch/` is
gitignored, and these two issues are *published evidence* — the scorecard and
`expected-findings.json` both depend on `issues/02`, and CI uploads the
artifacts that cite it. Untracked issue files could not carry that weight.
Phase 1 also must not edit anything outside `stats-validation/`, so the
app-side convention docs were left exactly as they are rather than amended.
Each issue file repeats this note in its own header, so a maintainer who
follows the documented convention, finds nothing under `.scratch/`, and then
finds these, knows immediately why they are here.

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
  *disappearing* is. The omission is total, not approximate — rewrite a
  `figura` to 99999 and `gate` still exits 0. That is only safe because a
  second gate owns the values; see **The freshness gate** below, and read
  `gate`'s own success message, which says what it did not check.
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

## The freshness gate, and why it is not `git diff`

    make -C stats-validation freshness

`gate` asks *"is the set of findings still the set we dispositioned?"*.
`freshness` asks the other half: *"is the evidence **committed** to the repo what
this commit's code regenerates — numbers included?"* It reads the artifact as
committed (`git show HEAD:stats-validation/results/findings.json`) and compares
it against the freshly built one:

- **structure exactly** — case ids, kinds, coverage counts, targets, run totals,
  and every finding's identity and kind. This reuses `gate.py`'s own
  `normalize()` and `diff()`, so the two gates cannot drift into disagreeing
  about what a finding *is*;
- **values to tolerance** — `figura` and `python` at `compare.py`'s own
  `REL_TOL` / `ABS_TOL`, through its own `close_enough()`. Non-numeric values
  (rendered cells, notes) are compared exactly: a string has no tolerance.

**A byte diff over `findings.json` would be wrong, not merely strict.** Local
(Homebrew R + Accelerate BLAS, a source-built numpy on Python 3.14) and CI
(Ubuntu R + OpenBLAS, manylinux wheels on 3.11) reproduce an iteratively fitted
estimate to roughly 1e-10, not to the last bit. A byte comparison of those digits
compares *environments*, and would fail the first CI run for a non-regression
while accusing the developer of committing a stale scorecard — the same false red
the baseline gate exists to avoid. So a 1e-15 wobble passes; a 1e-4 move fails; a
changed identity, kind or coverage count fails whatever the numbers do.

An **absent** committed baseline (the commit that first publishes the artifact,
or a checkout where it was never tracked) is reported and passes. A missing
regenerated `findings.json`, an unresolvable `--ref`, or no git at all is exit 2
— a gate that cannot answer its question must never render as "fresh".

**Published values are rounded to 9 significant digits.** `compare.py` rounds
`figura`/`python` on the way *into* `findings.json` (`PUBLISHED_SIGNIFICANT_DIGITS`)
— three orders tighter than `REL_TOL` (1e-6), so nothing the comparator judges
is affected, while the digits that are pure BLAS noise stop being committed.
The comparison itself runs on the full double; full precision stays in the
gitignored `results/*.figura-exact.json` and `results/*.python.json`. The
artifact says so inline (`_published_precision`) and so does the scorecard, so
no reader can conclude the harness *compared* at 9 digits. `results/scorecard.html`
is therefore still **byte**-diffed in CI: it renders only what `findings.json`
publishes, and `build_scorecard.py` reads no live state.

**Why 9 and not 12.** An earlier round rounded to 12 significant digits
(~1e-12 relative) on the theory that it was "a million times tighter than
`REL_TOL`" and therefore safe. It is not safe for the *byte diff*: 12 digits
is tight enough that a real cross-environment divergence at the scale CI is
expected to show (Ubuntu R + OpenBLAS vs local Homebrew R + Accelerate BLAS,
estimated ~1e-10) still changes the published digits, so `git diff --exit-code
scorecard.html` could go red on the very first CI run for a non-regression —
exactly the false-red class this whole gate exists to avoid.

Measured directly, with the real `compare.py::main()` + real
`build_scorecard.py::build()`, run end to end against a scratch copy of
`results/`: `logistic-dirty`'s real Path B `age` estimate
(`1.6648751058762834`, the published side of a genuine `DEFECT` finding) is
perturbed by a relative gap, the whole pipeline is rerun (comparator decides,
rounds, writes `findings.json`; the scorecard is rebuilt from it), and the
regenerated `scorecard.html` is sha256-compared byte for byte against the
unperturbed build — same case list, same code, only
`PUBLISHED_SIGNIFICANT_DIGITS` and the injected gap differ between the two
tables below:

    PUBLISHED_SIGNIFICANT_DIGITS = 12 (the old value)
    rel gap    published pair                        byte-identical
    1e-16      1.68264486127 vs 1.66487510588        True
    1e-13      1.68264486127 vs 1.66487510588        True
    1e-11      1.68264486127 vs 1.66487510589        False
    1e-10      1.68264486127 vs 1.66487510604        False
    1e-9       1.68264486127 vs 1.66487510754        False

    PUBLISHED_SIGNIFICANT_DIGITS = 9 (this round)
    rel gap    published pair                        byte-identical
    1e-16      1.68264486 vs 1.66487511              True
    1e-13      1.68264486 vs 1.66487511              True
    1e-11      1.68264486 vs 1.66487511              True
    1e-10      1.68264486 vs 1.66487511              True
    1e-9       1.68264486 vs 1.66487511              True

12 digits reproduces the original concern exactly (breaks at 1e-11 and
1e-10). At 9 digits both round-trip byte-identical, with margin to spare at
1e-9 too. A finer scan (same value, same pipeline) localizes where it finally
breaks:

    rel gap    byte-identical at 9 digits
    5e-9       True
    6.3e-9     False   <- smallest measured perturbation that still breaks it
    8e-9       False
    1e-7       False

**The gate's real, measured immunity threshold is ~6e-9 relative** for this
value — a perturbation has to reach that scale before it can flip a published
9th significant digit and therefore change `scorecard.html`'s bytes. (The
exact break point is a per-value rounding-boundary artifact — it depends on
where the specific double sits relative to the next representable 9-digit
string, not a single universal constant — but it is consistent with the
theoretical half-step of a 9-significant-digit round for a value of this
magnitude, ~5e-9 relative.) That is comfortably above the ~1e-10 environment
gap the reviewer estimated for Accelerate-vs-OpenBLAS — two orders of
magnitude of headroom — and still three to four orders below `REL_TOL`
(1e-6), so the comparator's verdicts never move.
`results/*.figura-exact.json` and `results/*.python.json` keep full precision
regardless — only the tracked, byte-diffed artifacts get the 9-digit cut.

CI (`.github/workflows/ci.yml`, job `validation`) runs, in order: `make test`;
`make clean all` with its status recorded but not obeyed; a check that
`results/logistic-dirty.figura.json` exists at all (it is gitignored, so it can
only be there if the pipeline really ran — without this, a failure *before*
`make clean` deletes anything leaves the tracked evidence intact and both gates
compare it against itself); `make gate`; `make freshness` plus a byte diff of
`scorecard.html`; and three separate artifact uploads. `webr-tier.json` is
excluded from both freshness checks — nothing in CI regenerates it, because the
webR tier is hand-run — but it is still uploaded. The uploads are split one file
per step because `if-no-files-found` is evaluated over the whole path list: three
paths in one step means a missing `webr-tier.json` warns about nothing. A missing
`findings.json` is a hard failure (exit 2) in both gates, which is what catches a
pipeline that died before the comparator wrote anything: the one real risk of not
obeying `all`'s status.

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

**The evidence is bound to the code it measured, in both directions.**
`webr-tier.json` records `commit` (the repo `HEAD` at run time, written ONLY by a
real run of `e2e/webr-parity.spec.js` — see that file's `repoCommit()` for the
invariant and the regression that once broke it) plus two digests, because there
are two independent ways this evidence can go stale:

- **`native_digest`** — a sha256 of the native `text` strings (from
  `results/<id>.figura.json`) that were actually compared against. A later
  `make all` that changes native output changes it.
- **`web_digest`** — a sha256 of the shipped app sources the tier drove:
  `web/index.html`, `web/styles.css`, and every `*.js` under `web/`, excluding
  `*.test.mjs` (never shipped — `index.html` loads no `.mjs`), the gitignored
  `web/R/` and `web/webr/` build copies, and the fonts/PNG/CNAME, whose bytes
  cannot change the DOM text the tier reads out of `#stats`. This closes the gap
  the digest-based note used to leave open: a change under `web/` can move what
  the *browser* computes while every native artifact stays byte-identical, and
  `native_digest` cannot see that.

The rule is a **glob, not a hand-written list**, and deliberately so. The app is
a single-page shell whose form registry statically imports every guided analysis,
so the true import closure from `index.html` is very nearly "every `.js` under
`web/`" anyway — a hand list would buy no precision and would silently go stale
the first time somebody adds a module, producing a *false parity* claim, the worst
direction to fail in. The cost, stated plainly: it over-triggers. A pure styling
change flags webR staleness even though no number moved. That is the safe
direction — the note says "re-run the gate", the gate is hand-run before a release
anyway, and it clears itself on the next run.

The scorecard shows the commit (short form) next to the runtime line, and — since
binding is only useful if staleness is actually visible, not just theoretically
detectable — it recomputes **both** digests from the files on disk and says so on
the page when either disagrees, in two separate sentences: "the native numbers
moved" and "the app moved" are different facts with different remedies. Each
digest is implemented twice, once in JS (the spec records it) and once in Python
(the scorecard recomputes it); a drift between the two would produce a *permanent
false staleness note*, so `test_scorecard.py` runs both implementations and
compares them — including on ids and filenames whose code-point and ICU
collation orders disagree, which is a bug that was really there (`localeCompare`
on the JS side against Python's `sorted()`).

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
all", which fired on literally every commit and was noise; the *useful* half of
what it covered — a `web/`-only change — is now carried by `web_digest` above,
as measurement rather than as a docstring. `build_scorecard.py` reads no live
state whatsoever: it is a function of files in the checked-out tree (`results/`
and `web/`), never of the clock, the environment, or `HEAD`.
`test_scorecard_is_a_pure_function_of_its_inputs` pins that.

Coverage is **2 of the 8 cases** — the two ratio-table analyses with a full
native-R display artifact to compare a rendered table against,
`logistic-confounding` and `cox-adjusted`. The other six are validated on the
native-R tiers above and are covered by **no** wasm-vs-native claim at all. The
scorecard states the same ratio in the rendered WebR tier section, so the page
cannot be read as whole-roster parity. The rest of the roster is Phase 2 — it
needs the shared-boot refactor of the existing suites.

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

**If you are implementing Path B: do not read `R/*.R`.** A port that reproduces
the same misreading of the spec proves nothing — which is exactly the limit
named in "How the clean room actually worked, and its limits" above, and the
reason the rule is worth keeping even though the spec, not the sources, is the
real single point of failure. If you find the spec ambiguous, record the
ambiguity in your `DECISIONS-<module>.md` and resolve it from the spec; do not
resolve it by looking.

Phase 1 never edits `R/` or `web/` — this harness is entirely new code and
data living under `stats-validation/`. Harness JS tests are run via
`stats-validation`'s own `Makefile` targets, not the repo's `npm run
test:unit` chain; they are a separate test surface and must not be appended
to that hand-maintained chain.
