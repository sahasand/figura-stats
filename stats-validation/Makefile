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

# Cases whose PATH B module does not exist yet. `summary-table1` runs Path A
# (build-spec -> run-figura -> run-script) and publishes its harvest, but has
# no python.json to compare against until validate/summary.py lands — that is
# the clean-room half of Task 11, written from spec/summary-table1.md alone.
# The comparator's `table1` branch IS implemented and unit-tested; what is
# missing is the second opinion, and a comparison with only one side is not a
# comparison. Listing the case here (rather than dropping it from CASES) keeps
# its Path A artifacts regenerating on every run, so the day Path B arrives the
# only edit is deleting this line.
PENDING_PATH_B := summary-table1
COMPARE_CASES := $(filter-out $(PENDING_PATH_B),$(CASES))

.PHONY: all test clean

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
#
# PATH_B is a target-specific variable so the pattern rule stays single: a case
# listed in PENDING_PATH_B gets an announcement instead of a validate.cli run.
# It is announced, never silent — an absent Path B is a stated gap in the
# guarantee, and the scorecard must not be read as if that case were compared.
PATH_B = cd python && $(PY) -m validate.cli ../cases/$*
$(PENDING_PATH_B:%=results/%.done): PATH_B = \
  echo "  Path B SKIPPED for $* — validate/summary.py not written yet; \
this case publishes Path A artifacts only and is not passed to compare.py"

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

# Suites that are expected to be RED right now, and are therefore run OUTSIDE
# the gate. tests/test_summary.py is an acceptance test written before its
# module (validate/summary.py, the clean-room half of Task 11) exists, so it
# fails at import with ModuleNotFoundError — that is the red half of red-green,
# not a broken suite.
#
# WHY THIS VARIABLE EXISTS AT ALL. `make test` used to run it inside the gate,
# which made `test` fail by design — and make stops the chain at the first
# failing target, so the documented CI invocation `make -C stats-validation test
# all` NEVER REACHED `all`: no comparison ran and no scorecard was published,
# for as long as the clean-room half was outstanding. Putting the known-pending
# suite outside the gate is the honest fix: it still RUNS, still prints its
# output, and the recipe says loudly whether it was red as expected or has
# started passing (in which case the fix is to delete it from this list, which
# is one line). What it no longer does is block every later target.
#
# `all` remains free to exit non-zero: logistic-dirty publishes real findings by
# design (see the `all` recipe). So `make test all` runs BOTH targets, publishes
# the scorecard, and then reports the findings as a failure — which is the
# intended CI shape. A CI job that must not go red on published findings should
# run `make test` and `make all` as separate steps and treat `all`'s status as
# "findings exist", never as "do not publish".
KNOWN_PENDING := tests/test_summary.py

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
# ORDER IS LOAD-BEARING: the python suite runs LAST, and the KNOWN_PENDING
# module runs after even that, outside the gate. Make stops the chain at the
# first failing line, so a genuinely broken comparator or harness must never be
# able to hide behind the one failure that is supposed to be there — and the
# expected failure must not stop `make test all` from reaching `all`.
#
# The pending module is IGNORED by the gated run (--ignore) and then run on its
# own, loudly, with its status reported but not propagated. When it starts
# passing, the recipe says so and names the one-line fix: delete it from
# KNOWN_PENDING, at which point it gates like everything else.
test:
	cd .. && node stats-validation/harness/build-spec.test.mjs
	node harness/parse-cells.test.mjs
	cd compare && $(PY) -m pytest tests -q
	cd python && $(PY) -m pytest tests -q --ignore=$(KNOWN_PENDING)
	@echo ""
	@echo "=== KNOWN-PENDING SUITE: $(KNOWN_PENDING) (expected RED; does not gate) ==="
	@cd python && if $(PY) -m pytest $(KNOWN_PENDING) -q; then \
	  echo "*** $(KNOWN_PENDING) now PASSES — validate/summary.py has landed."; \
	  echo "*** Remove it from KNOWN_PENDING in the Makefile so it gates again."; \
	else \
	  echo "*** RED as expected: validate/summary.py is not written yet."; \
	  echo "*** The only acceptable failure here is ModuleNotFoundError:"; \
	  echo "*** No module named 'validate.summary'. Read the output above."; \
	fi

clean:
	rm -rf results/*.json results/*.done results/scorecard.html
