# 09 — Cox table prints an HR the forest plot silently omits

Status: resolved
Type: task
Found: 2026-07-20, during review of `fix/cox-forest-and-preview` (introduced by issue 05's fix, knowingly)

## Problem

Issue 05 added `exp(upper) <= 1e6` to `.cox_forest_svg` (`R/cox.R:226`), copying
`.logistic_forest_svg`. But `.cox_hr_cell` (`R/cox.R:107-109`) has **no** magnitude rule —
it rejects only on a non-finite estimate/CI or a captured fit warning.

So a huge-but-finite, unwarned hazard ratio now prints a number in Table 3 and is **absent
from the forest plot**, with nothing in either output saying why. That is a reversed,
milder version of the disagreement issue 05 set out to remove.

`.logistic_or_cell` (`R/logistic.R:151`) *does* carry `hi > 1e6`, so logistic's table and
plot agree and cox's no longer do — a behavioral divergence between the two deliberate
near-clones.

## Why it was left

Closing it requires either:

- adding the 1e6 rule to `.cox_hr_cell`, which **turns currently-printed hazard ratios into
  "not reliably estimated"** — a change to shipped output that needs owner sign-off; or
- reverting the plot bound, which re-opens issue 05.

Shipping the asymmetry was the right call for that branch; recording it here so it stays a
deliberate state rather than a forgotten one.

## Fix

Decide, with the owner, whether cox's table should adopt the 1e6 reliability bound so the
two outputs agree and the two analyses stay parallel. If yes, expect the change to alter
Table 3 cells for extreme fits, and add a test pinning the new wording. See also issue 08,
which raises the same question for the lower tail in both analyses.

## Comments

Resolved with owner sign-off, on `main`, together with issue 08 — they were one
decision wearing two issue numbers.

Route taken: **adopt the bound in the table**, not revert it in the plot. Both analyses now
share a single predicate, `.ratio_reportable(est, lo, hi)` in `R/dispatch.R`, called by
`.cox_hr_cell`, `.logistic_or_cell`, `.cox_forest_svg` and `.logistic_forest_svg`. A table
and its figure can no longer disagree about which terms carry usable information, and cox
and logistic can no longer drift apart on the question.

Shipped output does change, as predicted: a hazard ratio whose CI runs past 1e6 (or, per
issue 08, below 1e-6) now reads "not reliably estimated" where it previously printed a
number.

One gap this opened had to be closed in the same change: with the old rule a cox cell only
went unreliable when the fit *warned*, and the warning had its own sentence. The bound
makes an **unwarned** fit produce refusals, so `fig_cox` gained the separation/collinearity
CAUTION that `fig_logistic` has always had — otherwise the table said "not reliably
estimated" with nothing anywhere explaining why. Tested both ways: present when a cell
refuses, absent for a healthy model.
