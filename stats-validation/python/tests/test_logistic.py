import numpy as np
import pandas as pd
from validate.logistic import fit_logistic, reportable


def _frame(seed=7, n=400):
    rng = np.random.default_rng(seed)
    stage = rng.choice(["I", "II"], size=n)
    x = (stage == "II").astype(float)
    logit = -1.0 + 1.2 * x
    y = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    return pd.DataFrame(
        {"resp": np.where(y == 1, "Yes", "No"), "stage": stage}
    )


def test_recovers_a_known_odds_ratio():
    df = _frame()
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    est = out["terms"]["stageII"]["est"]
    assert 2.4 < est < 4.4  # true OR = exp(1.2) = 3.32


def test_ci_uses_the_literal_1_96():
    df = _frame()
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    t = out["terms"]["stageII"]
    # log-CI must be symmetric about the log estimate to machine precision
    lo, hi, est = np.log(t["lo"]), np.log(t["hi"]), np.log(t["est"])
    assert abs((est - lo) - (hi - est)) < 1e-12


def test_increment_rescales_the_odds_ratio():
    rng = np.random.default_rng(3)
    age = rng.normal(60, 10, 500)
    y = rng.binomial(1, 1 / (1 + np.exp(-(-6 + 0.1 * age))))
    df = pd.DataFrame({"resp": np.where(y == 1, "Yes", "No"), "age": age})
    per1 = fit_logistic(df, "resp", "Yes", ["age"], {}, {})
    per10 = fit_logistic(df, "resp", "Yes", ["age"], {}, {"age": 10})
    assert abs(np.log(per10["terms"]["age"]["est"])
               - 10 * np.log(per1["terms"]["age"]["est"])) < 1e-9
    # the p-value is invariant to rescaling
    assert abs(per10["terms"]["age"]["p"] - per1["terms"]["age"]["p"]) < 1e-9


def test_counts_are_reported():
    df = _frame()
    df.loc[0, "stage"] = ""
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    assert out["n_dropped"] == 1
    assert out["n"] == len(df) - 1
    assert out["n_event"] == int((df.drop(index=0)["resp"] == "Yes").sum())


def test_unadjusted_and_adjusted_both_present():
    rng = np.random.default_rng(11)
    n = 500
    arm = rng.choice(["Standard care", "New treatment"], size=n)
    age = rng.normal(60, 10, n)
    logit = -4 + 0.05 * age + 0.4 * (arm == "New treatment")
    y = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    df = pd.DataFrame({
        "resp": np.where(y == 1, "Yes", "No"), "arm": arm, "age": age,
    })
    out = fit_logistic(df, "resp", "Yes", ["arm", "age"],
                       {"arm": "Standard care"}, {"age": 10})
    for key in ("armNew treatment", "age"):
        assert key in out["terms"]
        assert key in out["unadjusted"]
    assert 0.5 < out["c_statistic"] < 1.0


def test_perfect_separation_is_not_reportable():
    # Spec Reportability: estimate and both CI bounds finite, interval within
    # [1e-6, 1e6] — a perfectly separated covariate must fail this.
    df = pd.DataFrame({
        "resp": ["Yes"] * 20 + ["No"] * 20,
        "grp": ["A"] * 20 + ["B"] * 20,
    })
    out = fit_logistic(df, "resp", "Yes", ["grp"], {"grp": "A"}, {})
    cell = out["terms"]["grpB"]
    assert not reportable(cell)


def test_reportable_accepts_a_normal_cell():
    assert reportable({"est": 1.5, "lo": 1.1, "hi": 2.1, "p": 0.01})
    assert not reportable({"est": float("inf"), "lo": 1.0, "hi": 2.0, "p": 0.5})
    assert not reportable({"est": 2.0, "lo": 1e-9, "hi": 2.0, "p": 0.5})
