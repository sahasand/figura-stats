import math
import sys

import numpy as np
import pandas as pd
from scipy.stats import chi2 as chi2_dist

# Identical to R's sqrt(.Machine$double.eps), per spec/km-twoarm.md's median rule.
_MEDIAN_TOL = math.sqrt(sys.float_info.epsilon)


def _is_blank(value):
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return str(value).strip() == ""


def _group_curve(times, events):
    """Product-limit curve for one group's rows, at distinct EVENT times only.

    `times`/`events` are parallel lists over that group's kept rows. The
    tied-censoring convention (spec's Estimator section) falls out for free
    here: n(t) is counted directly from the raw per-row times (>= t) rather
    than from a risk set that has already had t's departures removed.
    """
    distinct_times = sorted(set(times))
    curve = []
    surv = 1.0
    for t in distinct_times:
        n_t = sum(1 for tt in times if tt >= t)
        d_t = sum(1 for tt, e in zip(times, events) if tt == t and e == 1.0)
        if d_t > 0:
            surv *= 1 - d_t / n_t
            curve.append({"t": t, "surv": surv, "at_risk": n_t})
    return curve


def _median_from_curve(curve):
    """R's survival:::survmean "minmin" rule, per spec/km-twoarm.md."""
    for i, point in enumerate(curve):
        if point["surv"] < 0.5 + _MEDIAN_TOL:
            t1, s1 = point["t"], point["surv"]
            if abs(s1 - 0.5) <= _MEDIAN_TOL:
                for later in curve[i + 1:]:
                    if later["surv"] < s1:
                        return (t1 + later["t"]) / 2
            return t1
    return None


def _logrank_p(group_names, group_times, group_events):
    """Ordinary (Mantel-Haenszel) log-rank test across >= 2 groups.

    Equal weight at every distinct pooled event time. Reduces to the
    familiar 2-group chi-square-on-1-df form when len(group_names) == 2.
    """
    if len(group_names) < 2:
        return None

    all_times = sorted(set(t for times in group_times.values() for t in times))
    observed = {g: 0.0 for g in group_names}
    expected = {g: 0.0 for g in group_names}
    covariance = {g1: {g2: 0.0 for g2 in group_names} for g1 in group_names}

    for t in all_times:
        n_g = {}
        d_g = {}
        for g in group_names:
            times = group_times[g]
            events = group_events[g]
            n_g[g] = sum(1 for tt in times if tt >= t)
            d_g[g] = sum(1 for tt, e in zip(times, events) if tt == t and e == 1.0)
        n_total = sum(n_g.values())
        d_total = sum(d_g.values())
        if d_total == 0 or n_total == 0:
            continue

        for g in group_names:
            observed[g] += d_g[g]
            expected[g] += d_total * n_g[g] / n_total

        if n_total > 1:
            factor = d_total * (n_total - d_total) / (n_total - 1)
            for g1 in group_names:
                for g2 in group_names:
                    delta = 1.0 if g1 == g2 else 0.0
                    covariance[g1][g2] += factor * (
                        delta * n_g[g1] / n_total
                        - (n_g[g1] * n_g[g2]) / (n_total ** 2)
                    )

    # Drop one group to get a non-singular (k-1)x(k-1) system; O-E sums to
    # zero across all groups, so the resulting chi-square is invariant to
    # which group is dropped.
    reduced = group_names[:-1]
    diff = np.array([observed[g] - expected[g] for g in reduced])
    cov = np.array([[covariance[g1][g2] for g2 in reduced] for g1 in reduced])
    chi2_stat = float(diff @ np.linalg.solve(cov, diff))
    df = len(reduced)
    return float(chi2_dist.sf(chi2_stat, df))


def fit_km(df, time, status, event_value, group):
    n_rows = len(df)
    blank = (
        df[time].map(_is_blank)
        | df[status].map(_is_blank)
        | df[group].map(_is_blank)
    )
    kept = df[~blank].reset_index(drop=True)
    n_dropped = n_rows - len(kept)

    parsed_times = kept[time].map(float)
    # Event coding is plain string equality only -- no numeric fallback, per
    # spec's deliberate departure from Cox/logistic's event-coding rule.
    events = kept[status].map(lambda cell: 1.0 if str(cell) == str(event_value) else 0.0)
    groups = kept[group].astype(str)

    group_names = sorted(groups.unique())
    group_times = {}
    group_events = {}
    for g in group_names:
        mask = groups == g
        group_times[g] = list(parsed_times[mask])
        group_events[g] = list(events[mask])

    curve = {g: _group_curve(group_times[g], group_events[g]) for g in group_names}
    medians = {g: _median_from_curve(curve[g]) for g in group_names}
    logrank_p = _logrank_p(group_names, group_times, group_events)

    return {
        "curve": curve,
        "medians": medians,
        "logrank_p": logrank_p,
        "n": len(kept),
        "n_event": int(events.sum()),
        "n_dropped": n_dropped,
    }
