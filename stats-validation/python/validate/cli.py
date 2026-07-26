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

from .cox import fit_cox
from .io import load_case
from .km import fit_km
from .logistic import fit_logistic

RESULTS = Path(__file__).resolve().parents[2] / "results"

# cox has no `outcome` role at all — it has `roles["time"]` and
# `roles["status"]`, both required — and fit_cox's positional order is
# `(df, time, status, event_value, covariates, ref_levels, increments)`
# (INTERFACES.md), which does not line up with fit_logistic's shape (a single
# `roles["outcome"]` column, positional order `(df, outcome, event_value,
# covariates, ref_levels, increments)`). So cox is dispatched as an EXPLICIT
# branch in run() below rather than through the generic FITTERS lookup.
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
    options = case.get("options", {})

    # km has no `covariates` role at all — it has `roles["time"]`,
    # `roles["status"]`, and `roles["group"]` — and fit_km's return shape
    # (medians/logrank_p/n/n_event/curve/n_dropped) carries no `terms`/
    # `unadjusted` dict for the display_terms/display_unadjusted block below
    # to key off. So km returns early, before the `covariates = ...` line.
    if figure == "km":
        out = fit_km(df, case["roles"]["time"], case["roles"]["status"],
                     options["event_value"], case["roles"]["group"])
        out["id"] = case["id"]
        out["figure"] = figure
        return out

    covariates = list(case["roles"]["covariates"])

    if figure == "cox":
        out = fit_cox(
            df,
            case["roles"]["time"],
            case["roles"]["status"],
            options["event_value"],
            covariates,
            options.get("ref_levels", {}),
            options.get("increments", {}),
        )
    else:
        fitter = FITTERS.get(figure)
        if fitter is None:
            raise SystemExit(
                f"no Path B implementation for figure {figure!r} "
                f"(implemented: {sorted(FITTERS)} + cox)")
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
