# One-command pipeline: raw CSV -> spec -> Path A (Figura) -> Path B (Python)
# -> comparator -> scorecard. Run from anywhere as `make -C stats-validation
# <target>`; every recipe line below assumes CURDIR is stats-validation/ (the
# directory make was invoked with -C into), and each line re-derives the cwd
# it needs from there — recipe lines do NOT share a shell, so a `cd` on one
# line never carries to the next.
#
# LOAD-BEARING GOTCHA: harness/run-figura.R and harness/run-script.R both call
# devtools::load_all(), which loads the `manuscriptfigures` package from the
# CURRENT working directory. They must run with the REPO ROOT as cwd, so their
# recipe lines `cd ..` first and address every path as `stats-validation/...`.
# The node build-spec step and the python steps run with stats-validation/ (or
# a subdirectory of it) as cwd instead, per their own path conventions.
PY := $(CURDIR)/.venv/bin/python
CASES := logistic-confounding cox-adjusted km-twoarm \
         groupcompare-numeric groupcompare-categorical groupcompare-dirty \
         logistic-dirty summary-table1

# validate/summary.py (the clean-room half of Task 11) has landed, so
# summary-table1 now runs Path B like every other case and is compared like
# every other case. There is no PENDING_PATH_B case left; COMPARE_CASES is
# the full case list.
COMPARE_CASES := $(CASES)

.PHONY: all test webr clean

# COMPARE MAY LEGITIMATELY EXIT 1. `logistic-dirty` is designed to publish real
# findings (the app-vs-exported-script divergence of issues/02), so a non-zero
# compare is the CORRECT pipeline outcome, not a crash. compare.py writes
# findings.json before it returns, so the scorecard must still be built from it
# — publishing the failing evidence is the whole point — while `make all` still
# reports the failure. Hence: capture compare's status, build the scorecard
# regardless, then exit with the captured status. (make itself then exits 2, its
# own fixed "a recipe failed" code, as it does for any failing recipe; what this
# structure guarantees is that a compare failure is never SWALLOWED and never
# skips the scorecard.) Recipe lines do not share a shell, so this is ONE line
# with continuations; and it `cd`s into compare/, so the scorecard is addressed
# absolutely via $(CURDIR).
#
# TWO THINGS THE ORDERING BUYS, both learned the hard way:
#   * the STALE-EVIDENCE DELETE. findings.json and scorecard.html are removed
#     before compare runs. If compare then dies before writing (a missing
#     artifact, a crash), there is NOTHING to publish rather than last run's
#     numbers sitting under this run's timestamp; build_scorecard.py says so in
#     one line instead of silently re-rendering the old file.
#   * the STATUS PRECEDENCE. compare's status wins when it is non-zero (the
#     findings are the news); otherwise the scorecard build's status is
#     surfaced, so a scorecard that failed to build can never be reported as a
#     clean run.
all: $(CASES:%=results/%.done)
	rm -f results/findings.json results/scorecard.html; \
	  cd compare && $(PY) compare.py $(COMPARE_CASES); status=$$?; \
	  $(PY) $(CURDIR)/build_scorecard.py; card=$$?; \
	  [ $$status -eq 0 ] || exit $$status; exit $$card

# Four steps per case, in order: build-spec -> run-figura.R -> run-script.R ->
# validate.cli. (Step five, compare + scorecard, runs once after every case's
# .done exists — see the `all` recipe above.)
PATH_B = cd python && $(PY) -m validate.cli ../cases/$*

results/%.done: cases/%/data.csv cases/%/case.json
	@mkdir -p results
	node harness/build-spec.mjs cases/$* > results/$*.spec.json
	cd .. && Rscript stats-validation/harness/run-figura.R $* \
	  stats-validation/results/$*.spec.json \
	  stats-validation/results/$*.figura.json
	cd .. && Rscript stats-validation/harness/run-script.R $* \
	  stats-validation/results/$*.figura.json \
	  stats-validation/cases/$* \
	  stats-validation/results/$*.figura-exact.json
	$(PATH_B)
	@touch $@

# validate/summary.py (the clean-room half of Task 11) has landed and all of
# tests/test_summary.py is green, so the KNOWN_PENDING carve-out that used to
# run it outside the gate is retired. It is now just another suite under
# python/tests, discovered and run like every other test_*.py there.
#
# Every suite, chained. CI runs `make -C stats-validation test all`.
#
# harness/build-spec.test.mjs hardcodes the fixture path
# "stats-validation/cases/logistic-confounding" (relative to the repo root,
# not to harness/), so — unlike every other test here — it must run with the
# REPO ROOT as cwd, same gotcha as the R steps above and for the same reason:
# a path baked into the test assumes a specific cwd.
#
# The scorecard's own smoke test (compare/tests/test_scorecard.py) rides
# along inside `cd compare && pytest tests -q` — it is discovered like any
# other test_*.py in that directory, so it needs no separate recipe line.
#
# ORDER IS LOAD-BEARING: the python suite runs LAST. Make stops the chain at
# the first failing line, so a genuinely broken comparator or harness must
# never be able to hide behind a later, unrelated failure.
#
# `all` remains free to exit non-zero: logistic-dirty publishes real findings by
# design (see the `all` recipe). So `make test all` runs BOTH targets, publishes
# the scorecard, and then reports the findings as a failure — which is the
# intended CI shape. A CI job that must not go red on published findings should
# run `make test` and `make all` as separate steps and treat `all`'s status as
# "findings exist", never as "do not publish".
test:
	cd .. && node stats-validation/harness/build-spec.test.mjs
	node harness/parse-cells.test.mjs
	cd compare && $(PY) -m pytest tests -q
	cd python && $(PY) -m pytest tests -q

# THE ONE TIER THAT IS NOT IN `all` AND NOT IN `test`, AND MUST NOT BE ADDED TO
# EITHER. Everything else here runs native R offline; this drives the shipped
# browser UI with R compiled to WebAssembly and compares what webR displays
# against the native-R display artifacts in results/. It needs a real Chromium
# and the network (Playwright downloads the webR runtime and its packages from
# the CDN on every cold run), which is exactly the slow/flaky combination
# CLAUDE.md keeps out of CI. It is a HAND-RUN RELEASE GATE: run it before a
# release, read results/webr-tier.json, then rebuild the scorecard.
#
# Both lines run from the REPO ROOT (`cd ..`), for two different reasons: the
# R->web/R copy is a repo-root build step (web/R is a gitignored copy of R/ and
# `npm run serve` serves web/), and the Playwright config's paths — including
# its webServer cwd — are anchored there too.
#
# The spec DELETES results/webr-tier.json before it runs, the same
# stale-evidence rule `all` applies to findings.json: a run that dies before
# writing must publish nothing, not last release's numbers under this
# release's date. Rebuild the scorecard afterwards (`make all`, or just
# `.venv/bin/python build_scorecard.py`) to publish the result. `make clean`
# deliberately spares webr-tier.json for the same reason — see `clean` below.
webr:
	cd .. && rm -rf web/R && cp -R R web/R
	cd .. && npx playwright test --config stats-validation/e2e/playwright.config.js

# results/webr-tier.json is deliberately NOT removed here: it is git-tracked
# evidence of a release gate that a `make clean` of the local pipeline has no
# business revoking. The webr target replaces it on its next run.
# The $(filter-out ...) keeps webr-tier.json: it is git-tracked evidence of a
# release gate that a `make clean` of the local pipeline has no business
# revoking (`rm -f` with no remaining arguments is a no-op, so an empty or
# absent results/ is fine). The webr target replaces it on its next run.
clean:
	rm -f $(filter-out results/webr-tier.json,$(wildcard results/*.json))
	rm -rf results/*.done results/scorecard.html
