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

**`test` is currently red on 17 diagnostics acceptance tests, by design.**
Task A14's in-repo half published the advisory-diagnostics contract — the
specs, `INTERFACES.md`, the harvester, the comparator and the case files —
ahead of the clean-room implementation, exactly as every earlier analysis was
staged. `python/tests/test_logistic.py` and `python/tests/test_cox.py` fail
with `KeyError: 'diagnostics'` and nothing else; the other 60 python tests, all
191 comparator tests and both JS suites are green. Two lines activate the rest
when `validate/logistic.py` and `validate/cox.py` return their `diagnostics`
blocks: the entries in `compare.py`'s `PENDING_PATH_B_DIAGNOSTICS`. Until then
the three affected cases show their diagnostics coverage as **DEFERRED** on
the scorecard rather than as met, so nothing claims to have been checked that
was not.

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
