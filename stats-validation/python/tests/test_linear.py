from pathlib import Path

import numpy as np
import pandas as pd
from validate.io import load_case
from validate.linear import fit_linear, reportable

# Computed in R (lm + confint + summary) on cases/linear-confounding/data.csv
# with arm ref "Standard care", stage ref "I", age per 10. Pasted from the
# Rscript block in the implementation plan, Task 13 Step 3.
R_REFERENCE = {
    "armNew treatment": {"est": -1.4749289119, "se": 0.2941844467, "lo": -2.0537437334, "hi": -0.8961140903, "p": 8.93151118e-07},
    "age": {"est": 0.8364545478, "se": 0.1440603163, "lo": 0.5530124854, "hi": 1.1198966102, "p": 1.559558276e-08},
    "stageII": {"est": 1.2996923770, "se": 0.3058273953, "lo": 0.6979697801, "hi": 1.9014149739, "p": 2.822232066e-05},
    "stageIII": {"est": 3.0004401569, "se": 0.3424563953, "lo": 2.3266491406, "hi": 3.6742311732, "p": 1.211757519e-16},
    "r_squared": 0.2460968579, "adj_r_squared": 0.2365234847,
    "shapiro_p": 0.5101217193, "bp_p": 0.2209419134, "cooks_influential": 18,
}
CASE = Path(__file__).resolve().parents[2] / "cases" / "linear-confounding"


def _rel(a, b, tol=1e-6):
    return abs(a - b) <= max(1e-9, tol * max(abs(a), abs(b)))


def test_reproduces_r_on_the_shipped_case():
    df, _ = load_case(str(CASE))
    out = fit_linear(df, "los", ["arm", "age", "stage"],
                     {"arm": "Standard care", "stage": "I"}, {"age": 10})
    for key in ("armNew treatment", "age", "stageII", "stageIII"):
        for q in ("est", "se", "lo", "hi", "p"):
            assert _rel(out["terms"][key][q], R_REFERENCE[key][q]), (key, q)
    assert _rel(out["r_squared"], R_REFERENCE["r_squared"])
    assert _rel(out["adj_r_squared"], R_REFERENCE["adj_r_squared"])
    assert _rel(out["diagnostics"]["shapiro_p"], R_REFERENCE["shapiro_p"], 1e-4)
    assert _rel(out["diagnostics"]["bp_p"], R_REFERENCE["bp_p"])
    assert out["diagnostics"]["cooks_influential"] == R_REFERENCE["cooks_influential"]
    assert out["n"] == 320 and out["n_dropped"] == 0
    assert out["diagnostics"]["aliased_caution"] is False


def _frame(seed=7, n=300):
    rng = np.random.default_rng(seed)
    arm = rng.choice(["A", "B"], size=n)
    age = rng.normal(60, 10, n)
    y = 5 + 0.1 * (age - 60) - 2 * (arm == "B") + rng.normal(0, 2, n)
    return pd.DataFrame({"y": y, "arm": arm, "age": age})


def test_recovers_a_known_coefficient_and_uses_the_t_quantile():
    from scipy.stats import t
    df = _frame()
    out = fit_linear(df, "y", ["arm", "age"], {"arm": "A"}, {})
    term = out["terms"]["armB"]
    assert -2.6 < term["est"] < -1.4
    half = t.ppf(0.975, len(df) - 3) * term["se"]
    assert _rel(term["hi"] - term["est"], half) and _rel(term["est"] - term["lo"], half)
    assert abs((term["hi"] - term["est"]) - 1.96 * term["se"]) > 1e-6, "must not be the normal quantile"


def test_increment_rescales_the_coefficient_and_not_p():
    df = _frame()
    per1 = fit_linear(df, "y", ["age"], {}, {})
    per10 = fit_linear(df, "y", ["age"], {}, {"age": 10})
    assert _rel(per10["terms"]["age"]["est"], 10 * per1["terms"]["age"]["est"])
    assert _rel(per10["terms"]["age"]["p"], per1["terms"]["age"]["p"])


def test_counts_and_blank_handling():
    df = _frame()
    df.loc[0, "age"] = ""
    df.loc[1, "y"] = "  "
    out = fit_linear(df, "y", ["arm", "age"], {"arm": "A"}, {})
    assert out["n_dropped"] == 2 and out["n"] == len(df) - 2


def test_aliased_column_is_unreportable_and_flagged():
    df = _frame()
    df["age2"] = df["age"] * 2
    out = fit_linear(df, "y", ["arm", "age", "age2"], {"arm": "A"}, {})
    assert out["diagnostics"]["aliased_caution"] is True
    assert not reportable(out["terms"]["age2"])
    assert reportable(out["terms"]["age"])
    assert reportable(out["unadjusted"]["age2"])


def test_reference_fallback_when_declared_level_is_absent():
    df = _frame()
    out = fit_linear(df, "y", ["arm"], {"arm": "Z"}, {})
    ref = "A" if (df["arm"] == "A").sum() >= (df["arm"] == "B").sum() else "B"
    assert list(out["terms"]) == ["arm" + ("B" if ref == "A" else "A")]


def test_diagnostics_shapes():
    df = _frame()
    d = fit_linear(df, "y", ["arm", "age"], {"arm": "A"}, {})["diagnostics"]
    assert set(d) == {"shapiro_p", "shapiro_triggered", "bp_p", "bp_triggered",
                      "obs_per_term", "obs_per_term_triggered", "vif", "vif_triggered",
                      "cooks_influential", "cooks_triggered", "aliased_caution"}
    assert d["vif"] is None, "fewer than two continuous covariates -> None, not {}"
    assert _rel(d["obs_per_term"], len(df) / 2)
    assert isinstance(d["cooks_influential"], int)


def test_shapiro_is_none_outside_its_size_window():
    rng = np.random.default_rng(1)
    n = 5001
    df = pd.DataFrame({"y": rng.normal(size=n), "x": rng.normal(size=n)})
    d = fit_linear(df, "y", ["x"], {}, {})["diagnostics"]
    assert d["shapiro_p"] is None and d["shapiro_triggered"] is False


def test_breusch_pagan_fires_on_a_funnel():
    rng = np.random.default_rng(3)
    x = np.linspace(1, 100, 400)
    y = 2 + 0.5 * x + rng.normal(0, 0.05 * x)
    d = fit_linear(pd.DataFrame({"y": y, "x": x}), "y", ["x"], {}, {})["diagnostics"]
    assert d["bp_triggered"] is True and d["bp_p"] < 0.05
