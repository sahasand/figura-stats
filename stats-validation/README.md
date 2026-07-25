# Statistical validation

Two independent implementations compute the same statistics from the same raw
CSV, and the comparison is published.

- **Path A** is Figura exactly as shipped: the real CSV parser, the real spec
  builders, and `render_figure()`.
- **Path B** is a Python implementation written from the prose spec in
  `spec/`, by an implementer who has not read `R/`.

Run everything:

    make -C stats-validation all

Read `results/scorecard.html` in a browser. It is self-contained and opens
from `file://`.

**If you are implementing Path B: do not read `R/*.R`.** Independence is the
only thing this exercise measures. A port that reproduces the same misreading
of the spec proves nothing.

Phase 1 never edits `R/` or `web/` — this harness is entirely new code and
data living under `stats-validation/`. Harness JS tests are run via
`stats-validation`'s own `Makefile` targets, not the repo's `npm run
test:unit` chain; they are a separate test surface and must not be appended
to that hand-maintained chain.
