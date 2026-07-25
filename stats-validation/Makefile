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
CASES := logistic-confounding

.PHONY: all test clean

all: $(CASES:%=results/%.done)
	cd compare && $(PY) compare.py $(CASES)
	$(PY) build_scorecard.py

# Five steps per case, in order: build-spec -> run-figura.R -> run-script.R ->
# validate.cli. (Step five, compare + scorecard, runs once after every case's
# .done exists — see the `all` recipe above.)
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
	cd python && $(PY) -m validate.cli ../cases/$*
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
test:
	cd .. && node stats-validation/harness/build-spec.test.mjs
	node harness/parse-cells.test.mjs
	cd python && $(PY) -m pytest tests -q
	cd compare && $(PY) -m pytest tests -q

clean:
	rm -rf results/*.json results/*.done results/scorecard.html
