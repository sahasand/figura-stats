# Establish the Kaplan–Meier Reporting Baseline

Type: research
Status: resolved
Label: `wayfinder:research`

## Question

According to authoritative clinical and statistical reporting guidance, which plots, statistics, labels, assumption disclosures, data-quality checks, and interpretation safeguards must the Kaplan–Meier Guided Analysis require, recommend, or avoid—and where does the current implementation differ?

## Answer

The Kaplan–Meier Guided Analysis must treat the output as a structured, reproducible analysis rather than a plot followed by an automatic p-value. It requires explicit endpoint, time-origin/unit, event/censoring, population, group, and reference semantics; strict no-silent-loss preflight validation; curves with pointwise uncertainty, censor marks, and a real risk table; descriptive estimates before qualified log-rank or optional Cox summaries; and warnings/limitations that remain attached to copied or exported material. Unsupported censoring structures, competing-risk questions, and unreliable estimates must be stopped or withheld with a method-specific explanation.

The current implementation is a sound browser/webR delivery base but falls short of that reporting baseline: it uses fixed headers and permissive CSV parsing, drops the requested risk table, omits confidence intervals and descriptive summaries, automatically reports a directionless HR without diagnostics, suppresses scientifically relevant warnings, and lacks numerical truth/edge-case tests and an explicit handoff.

Detailed required/recommended/avoid policies, citations, code gaps, and acceptance implications are in [Kaplan–Meier Reporting Baseline](../research/km-reporting-baseline.md).
