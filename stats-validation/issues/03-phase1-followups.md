# 03 — Phase-1 follow-ups, recorded but deliberately not fixed

Status: ready-for-agent
Type: task
Location: **`stats-validation/issues/`, not `.scratch/<slug>/issues/`.** This is a
deliberate deviation from `docs/agents/issue-tracker.md` and the repo `CLAUDE.md`.
`.scratch/` is gitignored, and Phase 1 must not edit anything outside
`stats-validation/`, so the convention docs were left unamended rather than updated to
mention this directory. See `stats-validation/README.md` §"Where the issue files live".
Found: 2026-07-26, during the final whole-branch review of the statistical-validation
harness (Phase 1).

## Why this file exists

The Phase-1 working ledger lived in `stats-validation/.sdd/`, which is **gitignored** and
therefore does not merge. Several small findings from the final review were correctly
judged *not worth fixing in the review's single fix wave* — each is either cosmetic, or a
latent robustness gap with no shipped case that reaches it, and fixing any of them risks
moving a published number for no evidential gain. Left only in the ledger they would
vanish at merge. They are recorded here instead.

**None of these is a bug in Figura.** Issues `01` and `02` are the app bugs this work
found. Everything below is about the harness itself.

---

## 1. `validate/logistic.py` infers covariate typing from `ref_levels` membership, with no guard

Path B decides whether a covariate is continuous or categorical by asking whether the
covariate's name appears as a key in the `ref_levels` mapping the case supplies. Path A
decides it from the **data** (`R/logistic.R`'s `.logistic_is_numeric` /
`R/cox.R`'s `.cox_is_numeric`: a column is numeric iff every non-blank cell parses).

The two agree on every shipped case because every shipped `case.json` declares a reference
level for exactly the categorical covariates. They would disagree the moment a case
declared a `ref_levels` entry for a numeric column, or omitted one for a categorical
column — and Path B would not notice: there is no assertion that the inferred typing
matches what the data supports, so the divergence would surface as a wrong term set or a
`MISSING_QUANTITY`, several steps downstream of the cause.

**Suggested fix:** derive the typing from the data in Path B too (the parseability rule is
already implemented for other purposes), and keep `ref_levels` for what it names — the
reference level — not for typing. Failing that, assert agreement between the two and fail
loudly.

**Why not now:** it is a real robustness gap with no shipped case that reaches it, and
changing the typing path touches every regression case's term set.

## 2. `blank_is_missing` is implicit at the logistic and cox call sites

`io.code_event(series, event_value, blank_is_missing=False)` defaults to `False`, and the
two call sites rely on the default rather than passing the value they mean. This is
exactly the asymmetry `issues/01` is about — logistic treats a blank outcome cell as
missing, Cox treats a blank status cell as censored — so the one place in Path B where the
distinction lives is the place it is least visible. A reader has to know the default to
know which rule is in force, and a future change to the default would silently flip Cox's
event coding.

**Suggested fix:** pass `blank_is_missing` explicitly at both call sites, with a one-line
comment naming the spec section each is implementing.

**Why not now:** pure legibility; no behaviour change, and the current behaviour is
correct and pinned by tests.

## 3. lifelines emits 133 warnings across the Python suite; a scoped `filterwarnings` is wanted

`cd python && ../.venv/bin/python -m pytest tests -q` currently reports
`83 passed, 133 warnings`. The warnings are library noise from lifelines' Cox fitting, not
signals about this code. The repo's R suite holds a **WARN 0** hard gate for exactly the
reason that noise trains people to stop reading warnings; the Python suite has no
equivalent, and 133 lines of noise is how a real deprecation warning gets missed.

**Suggested fix:** a **scoped** `filterwarnings` in `python/pytest.ini` — matched to
lifelines' specific warning classes/messages, never a blanket `ignore::Warning` — so the
count drops to zero and a new warning is visible again. The R suite's rule applies: if a
warning genuinely originates inside a library's internals, suppress only that library's
call, never your own model fitting.

**Why not now:** picking the right narrow filter needs the warning inventory read
properly, and a too-broad filter is worse than the noise.

## 4. `case.json` covariate order versus the spec's bullet order

For at least one case the covariate order in `case.json`'s `roles.covariates` is not the
order the spec lists the covariates in its Covariates bullets. Nothing depends on it today
— the comparator matches terms by name, not by position, and the app's own term order
comes from the fitted model — but the two orders being different for no reason is a trap:
a future reader reasonably assumes the spec's bullet order *is* the model's term order,
and any code that ever indexes covariates positionally would be wrong in a way no test
catches.

**Suggested fix:** make the spec's bullet order and `case.json`'s array order identical
for every case, and say in the spec that the order is the display/model order.

**Why not now:** it is a consistency fix with zero current behavioural effect, and
reordering `case.json` is exactly the kind of change that should not ride along in a
review wave whose stated constraint is that no published number may move.

## 5. Path B's `load_case` does not trim cells; Path A's parser does

Recorded during the same review, while reconciling the whitespace rules across the specs.

`web/lib/csv.js`'s `parseCsv` — the parser Path A really uses, via
`harness/build-spec.mjs` — trims **every** cell (`row[c] = (cells[j] ?? "").trim()`).
Path B's `io.load_case` reads the CSV with `pd.read_csv(..., dtype=str,
keep_default_na=False, na_filter=False)` and preserves cells exactly as written, and
`io._is_blank` tests `value == ""` only.

The two therefore disagree on a **whitespace-only cell in a text column**: Path A sees an
empty cell and drops the row; Path B sees a one-character value and keeps it, as its own
covariate level or group level. They agree on padded *numeric* cells (`pandas`'
`to_numeric` ignores surrounding whitespace, as R's coercion does), which is why
`logistic-dirty`'s two trailing-space `age` cells produce no divergence and the gap has
never shown up in a run.

No shipped case has a whitespace-only cell in a text column, so nothing published is
affected. The rule is now stated normatively in all six specs that have a Cell-reading
section, so an implementer reading the spec would get it right — but Path B as it stands
would not.

**Suggested fix:** trim in `load_case`, matching `parseCsv`, and add an acceptance test
with a whitespace-only categorical cell.

**Why not now:** it is a Path B change, and Path B changes belong in a clean-room dispatch
against the (now-corrected) spec, not in a review wave editing the module directly.
