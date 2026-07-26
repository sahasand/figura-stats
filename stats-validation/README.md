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
"findings exist, go read them", never "nothing was published". `test` is
green; the one suite that is red by design (`python/tests/test_summary.py`,
written before its module) runs outside the gate, loudly, so it can never
block `all` from running. See `KNOWN_PENDING` in the Makefile.

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
