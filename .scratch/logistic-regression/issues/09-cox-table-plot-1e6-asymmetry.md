# 09 — Cox table prints an HR the forest plot silently omits

Status: ready-for-agent
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
