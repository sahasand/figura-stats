# 04 — Downloadable Cox script can emit a reference level the app did not fit

Status: ready-for-agent
Type: task
Found: 2026-07-20, during the logistic-regression build

## Problem

`.cox_prep` (`R/cox.R:63-66`) falls back when the requested reference level is absent from the data after complete-case filtering:

```r
ref <- as.character(ref_levels[[cl]] %||% .cox_most_frequent(df[[cl]]))
...
if (!ref %in% lv) ref <- .cox_most_frequent(df[[cl]])
```

but `.cox_script` (`R/cox.R:273`) re-derives the reference from the **request** and never sees that fallback:

```r
ref <- qe(as.character(p$ref_levels[[cl]] %||% .cox_most_frequent(p$df[[cl]])))
```

So in the fallback case the downloaded `.R` script releveled against a different baseline than the table the user is looking at, and re-running it reproduces different HRs. The script's whole contract is that it is the code that actually ran.

## Fix

Read the fitted reference off the prepared data frame, as `.logistic_script` (`R/logistic.R:314-320`) already does:

```r
qe(levels(p$df[[cl]])[1])
```

Add a test where the requested reference level is dropped by complete-case filtering and assert the emitted script matches the fitted baseline.
