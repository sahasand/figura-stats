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
all: $(CASES:%=results/%.done)
	cd compare && $(PY) compare.py $(COMPARE_CASES); status=$$?; \
	  $(PY) $(CURDIR)/build_scorecard.py || exit 1; \
	  exit $$status

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
# ORDER IS LOAD-BEARING: the python suite runs LAST, because it is the one
# suite expected to be RED right now. tests/test_summary.py is an acceptance
# test written before its module (validate/summary.py, the clean-room half of
# Task 11) exists, so it fails at import with ModuleNotFoundError — by design,
# that is the red half of red-green. Make stops the chain at the first failing
# line, so running it last means a genuinely broken comparator or harness is
# never hidden behind the one failure that is supposed to be there.
# (python/pytest.ini's --continue-on-collection-errors keeps the OTHER five
# python modules reporting despite that collection error; see the comment
# there.) Delete nothing here when Path B lands — the line simply goes green.
test:
	cd .. && node stats-validation/harness/build-spec.test.mjs
	node harness/parse-cells.test.mjs
	cd compare && $(PY) -m pytest tests -q
	cd python && $(PY) -m pytest tests -q

clean:
	rm -rf results/*.json results/*.done results/scorecard.html
