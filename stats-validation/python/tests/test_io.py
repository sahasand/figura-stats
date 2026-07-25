import pandas as pd
from validate.io import code_event, complete_cases, treatment_dummies


def test_code_event_matches_string():
    s = pd.Series(["Yes", "No", "Yes", ""])
    assert code_event(s, "Yes").tolist() == [1, 0, 1, 0]


def test_blank_outcome_is_missing_not_a_non_event():
    s = pd.Series(["Yes", "", None])
    coded = code_event(s, "Yes", blank_is_missing=True)
    assert coded.tolist()[0] == 1
    assert pd.isna(coded.tolist()[1])
    assert pd.isna(coded.tolist()[2])


def test_numeric_equality_also_counts():
    s = pd.Series(["1", "0", "1.0"])
    assert code_event(s, "1").tolist() == [1, 0, 1]


def test_complete_cases_drops_blank_strings():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "", "z"]})
    kept, dropped = complete_cases(df, ["a", "b"])
    assert len(kept) == 2
    assert dropped == 1


def test_literal_NA_is_an_ordinary_value_not_missing():
    # Spec: "The literal string NA is an ordinary value, not missing."
    df = pd.DataFrame({"a": ["1", "2", "3"], "b": ["x", "NA", "z"]})
    kept, dropped = complete_cases(df, ["a", "b"])
    assert dropped == 0
    assert kept["b"].tolist() == ["x", "NA", "z"]


def test_declared_reference_absent_falls_back_to_most_frequent():
    # Spec: declared reference absent after filtering -> most frequent level.
    s = pd.Series(["B", "B", "B", "C", "C"])
    dummies, ref = treatment_dummies(s, "A")
    assert ref == "B"
    assert set(dummies.keys()) == {"C"}


def test_treatment_dummies_reference_first_rest_alphabetical():
    s = pd.Series(["b", "a", "c", "b", "a"])
    dummies, ref = treatment_dummies(s, "b")
    assert ref == "b"
    assert list(dummies.keys()) == sorted(dummies.keys())
    assert set(dummies.keys()) == {"a", "c"}
