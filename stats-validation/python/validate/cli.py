"""Run Path B for one case and write its results JSON.

Output shape (consumed by stats-validation/compare/compare.py):

  {id, figure,
   terms:              {<model term>: {est, se, lo, hi, p}},   adjusted
   unadjusted:         {<model term>: {est, se, lo, hi, p}},
   display_terms:      {<row key>:    {est, se, lo, hi, p}},   adjusted
   display_unadjusted: {<row key>:    {est, se, lo, hi, p}},
   n, n_event, n_dropped, c_statistic}

`terms`/`unadjusted` keep the raw model coefficient names (`armNew treatment`)
so the exact tier can match them against the R harvest. `display_*` re-keys the
same cells to the comparator's displayed-row keys (`arm:New treatment`, or the
bare covariate name for a numeric term) so the display tier can align rows.

This module never imports the comparator, and the comparator never imports it:
the row-key derivation below is deliberately a second, independent
implementation of the same rule. If the two ever disagree, the comparator
reports MISSING_QUANTITY on both sides rather than quietly matching a wrong row.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .io import load_case
from .logistic import fit_logistic

RESULTS = Path(__file__).resolve().parents[2] / "results"

# TODO(cox clean-room integration): once validate/cox.py lands (written from
# stats-validation/spec/cox-adjusted.md), import fit_cox here and register it
# as FITTERS["cox"] = fit_cox. Kept lazy/absent until then so this module
# keeps importing cleanly with no cox.py on disk.
FITTERS = {"logistic": fit_logistic}


def display_label(term: str, covariates) -> str:
    """A model coefficient name -> the comparator's displayed-row key.

    A categorical coefficient is the covariate name concatenated with the level
    and no separator, and levels contain spaces ("armNew treatment"), so the
    split is by LONGEST covariate prefix — never on whitespace. Longest first
    so a covariate named `stage` cannot claim `stage2`'s coefficients.
    """
    if term in covariates:
        return term  # numeric covariate: the coefficient IS the covariate
    matches = [c for c in covariates if term.startswith(c)]
    if not matches:
        # Unmatched: return the term verbatim so the comparator sees an
        # unmatched key and reports it, rather than a plausible wrong row.
        return term
    cov = max(matches, key=len)
    return f"{cov}:{term[len(cov):]}"


def run(case_dir: str) -> dict:
    df, case = load_case(case_dir)
    figure = case["figure"]
    if figure == "cox" and figure not in FITTERS:
        # Explicit, self-documenting stop rather than falling through to the
        # generic message below: cox is a REGISTERED figure (case.json,
        # build-spec.mjs, this dispatch site) whose Path B implementation is
        # simply not written yet — see the TODO above FITTERS.
        raise SystemExit(
            "Path B cox not yet present — validate/cox.py is written by the "
            "clean-room agent from stats-validation/spec/cox-adjusted.md")
    fitter = FITTERS.get(figure)
    if fitter is None:
        raise SystemExit(
            f"no Path B implementation for figure {figure!r} "
            f"(implemented: {sorted(FITTERS)})")

    covariates = list(case["roles"]["covariates"])
    options = case.get("options", {})
    out = fitter(
        df,
        case["roles"]["outcome"],
        options["event_value"],
        covariates,
        options.get("ref_levels", {}),
        options.get("increments", {}),
    )
    out["id"] = case["id"]
    out["figure"] = figure
    out["display_terms"] = {
        display_label(t, covariates): v for t, v in out["terms"].items()
    }
    out["display_unadjusted"] = {
        display_label(t, covariates): v for t, v in out["unadjusted"].items()
    }
    return out


def main(argv) -> int:
    if len(argv) != 1:
        raise SystemExit("usage: python -m validate.cli <case-dir>")
    result = run(argv[0])
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{result['id']}.python.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=False) + "\n")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
