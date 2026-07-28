import json
import os

import pandas as pd


def load_case(case_dir):
    data_path = os.path.join(case_dir, "data.csv")
    case_path = os.path.join(case_dir, "case.json")
    df = pd.read_csv(data_path, dtype=str, keep_default_na=False, na_filter=False)
    with open(case_path) as f:
        case = json.load(f)
    return df, case


def _try_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_blank(value):
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return value == ""


def code_event(series, event_value, blank_is_missing=False):
    event_num = _try_float(event_value)

    def classify(cell):
        if _is_blank(cell):
            return float("nan") if blank_is_missing else 0.0
        if cell == event_value:
            return 1.0
        cell_num = _try_float(cell)
        if cell_num is not None and event_num is not None and cell_num == event_num:
            return 1.0
        return 0.0

    return series.map(classify).astype(float)


def complete_cases(df, columns):
    mask = pd.Series(True, index=df.index)
    for col in columns:
        values = df[col]
        missing = values.isna() | values.apply(_is_blank)
        mask &= ~missing
    kept = df[mask]
    dropped = len(df) - len(kept)
    return kept, dropped


def to_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def treatment_dummies(values, reference):
    s = pd.Series(values)
    levels = list(s.unique())

    if reference in levels:
        ref = reference
    else:
        counts = s.value_counts()
        max_count = counts.max()
        candidates = sorted(level for level in counts.index if counts[level] == max_count)
        ref = candidates[0]

    other_levels = sorted(level for level in levels if level != ref)
    dummies = {level: (s == level).astype(float) for level in other_levels}
    return dummies, ref
