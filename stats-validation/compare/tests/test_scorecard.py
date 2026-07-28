"""Smoke test for build_scorecard.py (D11).

build_scorecard.py lives at the stats-validation/ repo root (sibling of
compare/, harness/, python/), not inside compare/ — it is imported here via a
path shim rather than a package relationship, deliberately: the scorecard is
a leaf consumer of findings.json, not part of the comparator package.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

STATS_VALIDATION = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STATS_VALIDATION))

import build_scorecard  # noqa: E402
from compare import (  # noqa: E402
    PUBLISHED_SIGNIFICANT_DIGITS, SRC_DISPLAY, SRC_EXACT, SRC_SCRIPT,
)

FIXTURE = {
    "cases": [
        {
            "id": "case-pass",
            "kind": "ratio_table",
            "compared": 10,
            "passed": True,
            "targets_met": True,
            "targets": {"adjusted_or": 1},
            "findings": [],
        },
        {
            # The logistic-dirty shape, in miniature: the EXACT tier fails
            # (the exported script's harvest disagrees with Path B) while the
            # display tier passes. The scorecard must attribute the defect to
            # the exported script, not to the displayed numbers.
            "id": "case-defect",
            "kind": "ratio_table",
            "compared": 5,
            "passed": False,
            "targets_met": False,
            "targets": {"adjusted_or": 0},
            "findings": [
                {
                    "code": "DEFECT",
                    "disposition": "defect",
                    "term": "<script>alert(1)</script>",
                    "quantity": "est",
                    "figura": "1.23",
                    "python": "9.99",
                    "note": "beyond rel 1e-6 / abs 1e-9",
                    "source": SRC_EXACT,
                },
                {
                    "code": "SCRIPT_DIVERGENCE",
                    "disposition": "defect",
                    "term": "age",
                    "quantity": "exported script cell",
                    "figura": "1.66 (1.24-2.23, p<0.001)",
                    "python": "1.68 (1.25-2.26, p<0.001)",
                    "note": "the exported .R does not reproduce the screen",
                    "source": SRC_SCRIPT,
                },
            ],
        },
        {
            "id": "case-missing-quantity",
            "kind": "ratio_table",
            "compared": 0,
            "passed": False,
            "targets_met": False,
            "targets": {"adjusted_or": 0},
            "findings": [
                {
                    "code": "MISSING_QUANTITY",
                    "disposition": "defect",
                    "term": "-",
                    "quantity": "n",
                    "figura": None,
                    "python": None,
                    "note": "Path B did not report n; the count could not "
                             "be compared",
                    "source": SRC_EXACT,
                }
            ],
        },
        {
            # Task 11's table1 kind, whose DECISION (mean vs median) is itself
            # a validated output. DECISION_MISMATCH is disposition "defect" per
            # compare.py's DISPOSITIONS, so DEFECT_CODES must pick it up
            # automatically — it is derived from that mapping, never hand-listed.
            "id": "case-decision",
            "kind": "table1",
            "compared": 5,
            "passed": False,
            "targets_met": True,
            "targets": {"decisions": 5},
            "findings": [
                {
                    "code": "DECISION_MISMATCH",
                    "disposition": "defect",
                    "term": "age",
                    "quantity": "decisions",
                    "figura": "mean",
                    "python": "median",
                    "note": "the two paths chose different summary statistics",
                    "source": SRC_DISPLAY,
                }
            ],
        },
    ],
    "total_compared": 20,
    "total_findings": 4,
}


def _build(tmp_path: Path, web_dir: Path | None = None) -> str:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(FIXTURE))
    out_path = build_scorecard.build(findings_path=findings_path,
                                     out_path=tmp_path / "scorecard.html",
                                     web_dir=web_dir)
    return out_path.read_text()


def test_tile_counts_correct(tmp_path):
    html = _build(tmp_path)
    # values compared, differences, defects, cases-meet-targets tiles.
    assert "<b>20</b>" in html  # total_compared
    # total_findings == defects here: DEFECT + SCRIPT_DIVERGENCE +
    # MISSING_QUANTITY + DECISION_MISMATCH
    assert "<b>4</b>" in html
    assert "<b>2/4</b>" in html  # 2 of 4 cases meet targets


def test_missing_quantity_counts_as_defect(tmp_path):
    """Regression pin for the reviewed bug: MISSING_QUANTITY is disposition
    "defect" per compare.py's own DISPOSITIONS mapping (compare.py classifies
    a coverage-failure finding the same as a value disagreement), and the
    scorecard's CSS styles .MISSING_QUANTITY identically red/bold to .DEFECT.
    A hand-picked DEFECT_CODES tuple that omitted MISSING_QUANTITY would
    render a red row while the defects tile claimed zero — this test fails
    if that regresses."""
    html = _build(tmp_path)
    # Every "defect"-disposition code must be counted: DEFECT,
    # SCRIPT_DIVERGENCE, MISSING_QUANTITY and DECISION_MISMATCH -> 4.
    assert "<b>4</b>" in html
    assert "class='MISSING_QUANTITY'" in html


def test_hostile_string_is_escaped(tmp_path):
    html = _build(tmp_path)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_defect_row_carries_fail_class(tmp_path):
    html = _build(tmp_path)
    assert "class='DEFECT'" in html


def test_targets_unmet_case_is_visibly_marked(tmp_path):
    html = _build(tmp_path)
    assert "TARGETS UNMET" in html
    assert "targets-unmet" in html
    # the passing, fully-covered case is marked distinctly, not as unmet.
    assert "targets met" in html


def test_no_dead_exact_pass_code_styled(tmp_path):
    """The comparator never emits EXACT_PASS (see compare.py's DISPOSITIONS
    comment), so the scorecard must not style it as a CSS selector or emit it
    as a row class — a prose mention explaining the omission is fine."""
    html = _build(tmp_path)
    assert ".EXACT_PASS" not in html
    assert "class='EXACT_PASS'" not in html


def test_webr_section_renders_honest_empty_state(tmp_path):
    html = _build(tmp_path)
    assert "Not yet run for this release" in html
    # ...and says how to produce one, including WHY it is not in `make all`.
    assert "make -C stats-validation webr" in html


# The shape stats-validation/e2e/webr-parity.spec.js writes: one identical case
# and one drifting one, so both renderings are pinned by the same fixture. The
# drifting values are the ones the tier's own negative-control run produced.
WEBR_TIER = {
    "runtime": "webR 0.6.1-dev+7603db7 (R 4.6.0)",
    # The REAL shape of this field, module URL and all — results/webr-tier.json
    # records where the version string came from, and that provenance is a
    # `https://` URL rendered as escaped text on the public page. A fixture that
    # dropped it would let the no-egress test (which greps every href/src) run
    # against a page containing no URL at all, and pass by having nothing to
    # find. See test_web_page_issues_no_external_request.
    "runtime_source": (
        "read from the WebR instance's own version fields, from the module the "
        "app loads (https://webr.r-wasm.org/latest/webr.mjs); the page itself "
        "prints no version string."),
    "date": "2026-07-26",
    "cases": [
        {
            "id": "cox-adjusted",
            "identical": True,
            "cells_compared": 13,
            "differing_cells": [],
        },
        {
            "id": "logistic-confounding",
            "identical": False,
            "cells_compared": 23,
            "differing_cells": [
                {
                    "term": "<script>alert(2)</script>",
                    "column": "adjusted",
                    "native": "0.51 (0.28-0.91, p=0.023)",
                    "webr": "0.50 (0.28-0.91, p=0.023)",
                },
                {
                    "term": "(methods paragraph)",
                    "column": "sentence 3",
                    "native": "C-statistic = 0.67.",
                    "webr": "C-statistic = 0.68.",
                },
            ],
        },
    ],
}


def _build_with_webr(tmp_path, payload=None, web_dir=None):
    (tmp_path / "webr-tier.json").write_text(
        json.dumps(WEBR_TIER if payload is None else payload))
    return _build(tmp_path, web_dir=web_dir)


def test_webr_section_renders_the_real_file(tmp_path):
    """Runtime, date, and a per-case identical/drift verdict with the number of
    cells behind it — not a raw JSON dump the reader has to parse by eye."""
    html = _build_with_webr(tmp_path)
    assert "Not yet run for this release" not in html
    assert "webR 0.6.1-dev+7603db7 (R 4.6.0)" in html
    assert "2026-07-26" in html
    assert "cox-adjusted" in html
    assert "IDENTICAL" in html
    assert "13 displayed cells matched native R exactly" in html
    assert "2 of 23 cells differ" in html


def test_webr_drift_row_is_visually_distinct_from_an_identical_one(tmp_path):
    """A drifting case must be styled like a defect, not like a footnote: the
    tier exists because a wasm-vs-native difference in a displayed number is a
    finding, and a reader skimming the section must not read one as a pass."""
    html = _build_with_webr(tmp_path)
    assert "class='webr-drift'>DRIFT" in html
    assert "class='webr-identical'>IDENTICAL" in html
    # ...and both classes reach the CSS, or the "distinct" claim is decorative.
    assert ".webr-drift" in html
    assert ".webr-identical" in html


def test_webr_drift_names_the_two_values(tmp_path):
    """"DRIFT" alone is unactionable. The cell, and both numbers, must be on
    the page so the reader can judge the SIZE of the difference."""
    html = _build_with_webr(tmp_path)
    assert "0.51 (0.28-0.91, p=0.023)" in html
    assert "0.50 (0.28-0.91, p=0.023)" in html
    assert "sentence 3" in html


def test_webr_runtime_provenance_is_shown(tmp_path):
    """The page prints no webR version, so the tier records how it identified
    the runtime. Rendering it keeps the runtime line from reading as an
    unsourced claim. (Asserted without the apostrophe: `esc` escapes it to
    `&#x27;`, which is correct output, not a missing string.)"""
    assert "read from the WebR instance" in _build_with_webr(tmp_path)


def test_webr_hostile_string_is_escaped(tmp_path):
    html = _build_with_webr(tmp_path)
    assert "<script>alert(2)</script>" not in html
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in html


def test_webr_file_that_is_not_json_says_so_rather_than_crashing(tmp_path):
    (tmp_path / "webr-tier.json").write_text("{not json")
    html = _build(tmp_path)
    assert "could not be read as JSON" in html


def test_webr_file_with_no_cases_does_not_render_an_empty_pass(tmp_path):
    """A run that wrote the file but listed no cases has gated nothing. An
    empty table would read as "no problems found"."""
    html = _build_with_webr(
        tmp_path, {"runtime": "webR x", "date": "2026-07-26", "cases": []})
    assert "lists no cases" in html
    # The verdict CLASS is the thing that must be absent — the words IDENTICAL
    # and DRIFT also appear in the CSS comment explaining how they are styled.
    assert "class='webr-identical'" not in html
    assert "class='webr-drift'" not in html


# Fix-round fixture: a case that ABORTED with a structural precondition
# failure (a row-count mismatch), alongside one that ran clean. This is the
# fix for "structural drift publishes nothing": before it, a precondition
# failure aborted the whole spec before webr-tier.json was ever written, so
# this state rendered identically to "not yet run for this release" — the
# empty-state branch, not a distinct row.
WEBR_TIER_ABORTED = {
    "runtime": "webR 0.6.1-dev+7603db7 (R 4.6.0)",
    "runtime_source": "read from the WebR instance's own version fields",
    "date": "2026-07-26",
    "commit": "815fa79d40d5bcb1a9cd5e3115694e51d58bd7b2",
    "cases": [
        {
            "id": "cox-adjusted",
            "identical": True,
            "cells_compared": 13,
            "differing_cells": [],
        },
        {
            "id": "logistic-confounding",
            "aborted": True,
            "reason": "webR tier precondition failed: webR table row count "
                      "(5) differs from native R (6)",
        },
    ],
}


def test_webr_aborted_case_is_rendered_distinctly(tmp_path):
    """An ABORTED case must be its own visible verdict, not silently missing
    and not folded into IDENTICAL/DRIFT — see the fixture's docstring for why
    this state existing at all is the fix."""
    html = _build_with_webr(tmp_path, WEBR_TIER_ABORTED)
    assert "Not yet run for this release" not in html   # ran; must not read as unrun
    assert "ABORTED" in html
    assert "class='webr-aborted'>ABORTED" in html
    assert ".webr-aborted" in html                       # ...and it reaches the CSS
    assert "row count" in html                            # the reason is shown
    # The other, non-aborted case in the same file still renders its own
    # verdict — an abort on one case must not swallow the other's evidence.
    assert "class='webr-identical'>IDENTICAL" in html


def test_webr_aborted_verdict_is_distinguishable_from_drift(tmp_path):
    """ABORTED and DRIFT are both "bad", but they are not the same finding —
    ABORTED means no comparison happened at all. They must not share a CSS
    class, or a reader cannot tell "no cells were compared" from "cells were
    compared and some disagreed"."""
    html = _build_with_webr(tmp_path, WEBR_TIER_ABORTED)
    assert "class='webr-drift'" not in html
    assert "class='webr-aborted'" in html


def test_webr_commit_is_shown(tmp_path):
    """The evidence file names the repo commit it was measured against
    (finding: "the artifact binds to no app version/native baseline"), so a
    reader can tell whether native output has moved on since."""
    html = _build_with_webr(tmp_path, WEBR_TIER_ABORTED)
    assert "815fa79d40d5" in html   # shown short, first 12 hex chars


def test_webr_missing_commit_renders_without_crashing_or_a_stray_dot(tmp_path):
    """Older webr-tier.json files (written before the commit field existed)
    must still render — no crash, and no dangling " · commit" separator with
    nothing after it."""
    html = _build_with_webr(tmp_path)   # the original WEBR_TIER fixture, no commit
    assert "commit <code>" not in html


# THE GUARD's own tests. The regression this defends against was real: commit
# 2997e1b's offline patch to webr-tier.json re-ran `git rev-parse HEAD` and
# clobbered `commit` from 815fa79d40d5bcb1a9cd5e3115694e51d58bd7b2 (the tree
# the browser actually ran against) to 6c7744dfd642af01d525d4788e4b644b35938314
# (a later, metadata-only commit the browser never saw) — a silent wrong claim.
#
# The guard used to answer that by comparing `commit` against live
# `git rev-parse HEAD`. It no longer does, for two reasons argued in full in
# build_scorecard._stale_native_digest: a HEAD comparison is DEFEATED by the
# very clobber it was written for (the two hashes now agree, so no note), and
# it made scorecard.html un-regenerable — committing the file advances HEAD, so
# the tracked copy permanently disagreed with its own rebuild and the CI
# freshness gate could never be green. The guard now compares `native_digest`
# against the same digest recomputed from results/<id>.figura.json, which is
# both deterministic and a direct statement about the numbers themselves.
def _write_native(tmp_path, texts: dict[str, str]) -> None:
    """The native-R display artifacts the webR tier compared against."""
    for case_id, text in texts.items():
        (tmp_path / f"{case_id}.figura.json").write_text(
            json.dumps({"text": text}))


NATIVE_TEXTS = {"cox-adjusted": "native cox table\n",
                "logistic-confounding": "native logistic table\n"}


def test_webr_matching_native_digest_shows_no_staleness_note(tmp_path):
    """The native artifacts on disk are the ones the gate was measured against:
    the evidence is current, so no staleness note — just the plain commit line."""
    _write_native(tmp_path, NATIVE_TEXTS)
    payload = dict(WEBR_TIER_ABORTED)
    payload["cases"] = [{"id": cid, "identical": True, "cells_compared": 1,
                         "differing_cells": []} for cid in NATIVE_TEXTS]
    payload["native_digest"] = build_scorecard._native_digest(
        tmp_path, list(NATIVE_TEXTS))
    html = _build_with_webr(tmp_path, payload)
    # The CSS rule (".webr-stale { ... }") is always present in the stylesheet
    # — only the RENDERED marker (the class attribute on a <p>) must be absent.
    assert 'class="webr-stale"' not in html


def test_webr_moved_native_output_shows_staleness_note(tmp_path):
    """A later `make all` changed the native numbers the webR run was compared
    against. The page must say so plainly instead of continuing to claim parity
    with values that no longer exist."""
    _write_native(tmp_path, NATIVE_TEXTS)
    payload = dict(WEBR_TIER_ABORTED)
    payload["cases"] = [{"id": cid, "identical": True, "cells_compared": 1,
                         "differing_cells": []} for cid in NATIVE_TEXTS]
    payload["native_digest"] = build_scorecard._native_digest(
        tmp_path, list(NATIVE_TEXTS))
    _write_native(tmp_path, {**NATIVE_TEXTS,
                             "cox-adjusted": "native cox table CHANGED\n"})
    html = _build_with_webr(tmp_path, payload)
    assert 'class="webr-stale"' in html
    assert "have changed since it ran" in html
    assert payload["native_digest"][:19] in html


def test_webr_clobbered_commit_does_not_defeat_the_staleness_note(tmp_path):
    """The exact 2997e1b regression: `commit` is overwritten with a value the
    browser never ran against. That edit cannot touch `native_digest`, so moved
    native output is still reported — which a HEAD comparison could not do."""
    _write_native(tmp_path, NATIVE_TEXTS)
    payload = dict(WEBR_TIER_ABORTED)
    payload["cases"] = [{"id": cid, "identical": True, "cells_compared": 1,
                         "differing_cells": []} for cid in NATIVE_TEXTS]
    payload["native_digest"] = build_scorecard._native_digest(
        tmp_path, list(NATIVE_TEXTS))
    payload["commit"] = "f" * 40          # clobbered
    _write_native(tmp_path, {**NATIVE_TEXTS,
                             "cox-adjusted": "native cox table CHANGED\n"})
    html = _build_with_webr(tmp_path, payload)
    assert 'class="webr-stale"' in html


def test_webr_absent_native_artifacts_fabricate_no_staleness_claim(tmp_path):
    """No results/<id>.figura.json on disk (a scorecard built without the
    pipeline's intermediates): the digest is not computable, so the page says
    nothing rather than declaring staleness it cannot demonstrate."""
    payload = dict(WEBR_TIER_ABORTED)
    payload["native_digest"] = "sha256:" + "0" * 64
    html = _build_with_webr(tmp_path, payload)
    assert 'class="webr-stale"' not in html


# --------------------------------------------------------------------------
# build_scorecard._stale_web_digest — the staleness direction `native_digest`
# CANNOT see.
#
# A change under web/ can move what the browser computes or displays while every
# native-R artifact stays byte-identical. `native_digest` then still agrees, and
# the page keeps claiming parity for an app the browser was never driven
# against. That gap was previously carried by a docstring; these tests are the
# evidence that it is now measured.
# --------------------------------------------------------------------------

def _write_web(root: Path, files: dict[str, str]) -> Path:
    """A miniature web/ tree. Keys are relative POSIX paths."""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


WEB_FILES = {
    "index.html": "<main></main>",
    "styles.css": ":root{--accent:#0d6b63}",
    "app.js": "export const forms = {};",
    "lib/csv.js": "export function parseCsv() {}",
    "guided/logistic/spec.js": "export function buildSpec() {}",
    # Excluded by the rule: a test file, a gitignored R build copy, a font.
    "lib/csv.test.mjs": "// unit test",
    "R/logistic.R": "fig_logistic <- function(spec) NULL",
    "fonts/ibm-plex.woff2": "not-really-a-font",
}


def _webr_payload_with_web(tmp_path, web_dir):
    payload = dict(WEBR_TIER_ABORTED)
    payload["cases"] = [{"id": cid, "identical": True, "cells_compared": 1,
                         "differing_cells": []} for cid in NATIVE_TEXTS]
    payload["native_digest"] = build_scorecard._native_digest(
        tmp_path, list(NATIVE_TEXTS))
    payload["web_digest"] = build_scorecard._web_digest(web_dir)
    return payload


def test_web_digest_agreeing_shows_no_staleness_note(tmp_path):
    """The app on disk is the app the gate was driven through: nothing to say."""
    _write_native(tmp_path, NATIVE_TEXTS)
    web = _write_web(tmp_path / "web", WEB_FILES)
    html = _build_with_webr(tmp_path, _webr_payload_with_web(tmp_path, web),
                            web_dir=web)
    assert 'class="webr-stale"' not in html


def test_a_web_only_change_shows_a_staleness_note(tmp_path):
    """THE GAP THIS CLOSES. Native output is untouched — `native_digest` still
    agrees — but `web/app.js` moved, so the published webR evidence describes a
    browser run of a tree that is no longer shipped."""
    _write_native(tmp_path, NATIVE_TEXTS)
    web = _write_web(tmp_path / "web", WEB_FILES)
    payload = _webr_payload_with_web(tmp_path, web)
    (web / "app.js").write_text("export const forms = {logistic: 1};")
    html = _build_with_webr(tmp_path, payload, web_dir=web)
    assert 'class="webr-stale"' in html
    assert "the shipped app has changed" in html
    assert payload["web_digest"][:19] in html
    # And it must be its own sentence, not folded into the native-digest note:
    # the two facts have different remedies.
    assert "have changed since it ran" not in html


def test_a_test_file_or_build_copy_change_is_not_web_staleness(tmp_path):
    """The rule must not cry wolf on things the browser never loads: a unit test
    (index.html loads no .mjs) or the gitignored web/R build copy, whose R
    sources are already covered by `native_digest`."""
    _write_native(tmp_path, NATIVE_TEXTS)
    web = _write_web(tmp_path / "web", WEB_FILES)
    payload = _webr_payload_with_web(tmp_path, web)
    (web / "lib" / "csv.test.mjs").write_text("// CHANGED unit test")
    (web / "R" / "logistic.R").write_text("fig_logistic <- function(spec) 999")
    (web / "fonts" / "ibm-plex.woff2").write_text("different-bytes")
    html = _build_with_webr(tmp_path, payload, web_dir=web)
    assert 'class="webr-stale"' not in html


def test_a_new_web_module_moves_the_digest(tmp_path):
    """Why the rule is a glob and not a hand-written list: a list would keep
    claiming parity the first time somebody adds a module."""
    web = _write_web(tmp_path / "web", WEB_FILES)
    before = build_scorecard._web_digest(web)
    (web / "lib" / "newthing.js").write_text("export const c = 3;")
    assert build_scorecard._web_digest(web) != before


def test_a_webr_file_without_web_digest_renders_exactly_as_before(tmp_path):
    """Every webr-tier.json written before this field existed — including the one
    currently committed — must render with no note and no crash."""
    _write_native(tmp_path, NATIVE_TEXTS)
    payload = dict(WEBR_TIER_ABORTED)
    payload["cases"] = [{"id": cid, "identical": True, "cells_compared": 1,
                         "differing_cells": []} for cid in NATIVE_TEXTS]
    payload["native_digest"] = build_scorecard._native_digest(
        tmp_path, list(NATIVE_TEXTS))
    assert "web_digest" not in payload
    html = _build_with_webr(tmp_path, payload, web_dir=tmp_path / "nonexistent")
    assert 'class="webr-stale"' not in html


def test_an_absent_web_tree_fabricates_no_staleness_claim(tmp_path):
    """A checkout without web/ (or an empty one) must say nothing, not declare
    staleness it cannot demonstrate."""
    assert build_scorecard._web_digest(tmp_path / "nope") is None
    (tmp_path / "empty-web").mkdir()
    assert build_scorecard._web_digest(tmp_path / "empty-web") is None
    _write_native(tmp_path, NATIVE_TEXTS)
    payload = dict(WEBR_TIER_ABORTED)
    payload["web_digest"] = "sha256:" + "0" * 64
    html = _build_with_webr(tmp_path, payload, web_dir=tmp_path / "nope")
    assert 'class="webr-stale"' not in html


# --------------------------------------------------------------------------
# The two digests are implemented TWICE — once in JavaScript (the spec records
# them) and once in Python (the scorecard recomputes them). A drift between the
# two produces a PERMANENT false staleness note on evidence that is perfectly
# current, and nothing else would ever fail. So the agreement is pinned by
# running both.
#
# The sort order is the real hazard, and it bit once already: the JS side used
# `localeCompare` (ICU collation) against Python's `sorted()` (code point). The
# two disagree on ids differing only in punctuation or case.
# --------------------------------------------------------------------------

E2E = STATS_VALIDATION / "e2e" / "compare-text.mjs"

# Verified adversarial for the two orderings: ICU weights punctuation below
# letters and orders '_' before '-' and '-' before '+', where code points do the
# opposite ('+' U+002B < '-' U+002D < '_' U+005F). Sorting these four ids with
# `localeCompare` and with `<` produces two DIFFERENT orders, so a digest built
# over them catches the bug; a plain `logistic-*` / `cox-*` roster would not.
#
# Deliberately no case-only pair (`Logistic-dirty` vs `logistic-dirty`), even
# though ICU and code points disagree there too: `_native_digest` reads
# results/<id>.figura.json, and on a case-insensitive filesystem (macOS APFS,
# where this suite also runs) the two ids would collide onto ONE file and the
# test would fail for a reason that has nothing to do with sort order.
ADVERSARIAL_IDS = ["summary-table1", "summary_table1",
                   "cox-adjusted", "cox+adjusted"]


def _node(script: str) -> str:
    import subprocess
    proc = subprocess.run(["node", "--input-type=module", "-e", script],
                          cwd=STATS_VALIDATION, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_native_digest_agrees_with_the_javascript_on_adversarial_ids(tmp_path):
    """The finding this pins: `sorted()` (code point) vs `localeCompare` (ICU)
    diverge, so the two implementations would hash the same inputs in different
    orders and the scorecard would report permanent staleness. These four ids
    are chosen so the two orderings genuinely disagree — a plain
    `logistic-*`/`cox-*` roster would pass even with the bug present."""
    texts = {case_id: f"table for {case_id}\n" for case_id in ADVERSARIAL_IDS}
    _write_native(tmp_path, texts)
    python_digest = build_scorecard._native_digest(tmp_path,
                                                   list(texts))  # unsorted
    js = _node(f"""
      import {{ nativeDigest }} from {json.dumps(str(E2E))};
      const texts = {json.dumps(texts)};
      const cases = Object.entries(texts).map(([id, text]) => ({{ id, text }}));
      process.stdout.write("sha256:" + nativeDigest(cases));
    """)
    assert python_digest == js


def test_web_digest_agrees_with_the_javascript_implementation(tmp_path):
    """Same hazard, same pin, for the web/ digest — including a filename pair
    the two sort orders disagree about, so the path sort is tested too."""
    files = dict(WEB_FILES)
    # The same '-' vs '_' divergence ADVERSARIAL_IDS uses, as FILENAMES, so the
    # path sort is pinned too and not merely the file set. No case-only pair, for
    # the case-insensitive-filesystem reason noted above.
    files["lib/model-form.js"] = "export const a = 1;"
    files["lib/model_form.js"] = "export const b = 2;"
    web = _write_web(tmp_path / "web", files)
    js = _node(f"""
      import {{ webDigest }} from {json.dumps(str(E2E))};
      process.stdout.write("sha256:" + webDigest({json.dumps(str(web))}).digest);
    """)
    assert build_scorecard._web_digest(web) == js


def test_web_digest_of_the_real_web_tree_agrees_with_the_javascript():
    """And on the actual repo, not only on fixtures — the tree the tier really
    digests, with its real font/PNG/CNAME/test-file mix."""
    web = STATS_VALIDATION.parent / "web"
    if not web.is_dir():
        pytest.skip("no web/ in this checkout")
    js = _node(f"""
      import {{ webDigest }} from {json.dumps(str(E2E))};
      const out = webDigest({json.dumps(str(web))});
      process.stdout.write("sha256:" + out.digest + " " + out.files.length);
    """)
    digest, count = js.split()
    assert build_scorecard._web_digest(web) == digest
    assert int(count) > 10, "the glob found suspiciously few app sources"


def test_the_published_precision_is_documented_on_the_page(tmp_path):
    """compare.py rounds measured values to PUBLISHED_SIGNIFICANT_DIGITS on the
    way into findings.json. A reader must not be able to conclude the COMPARISON
    was made at that precision — it was made on the full double."""
    html = _build(tmp_path)
    assert f"rounded to {PUBLISHED_SIGNIFICANT_DIGITS} significant digits" in html
    assert "comparison itself ran at full double precision" in html


def test_scorecard_is_a_pure_function_of_its_inputs(tmp_path):
    """THE PRECONDITION FOR THE FRESHNESS GATE. CI rebuilds scorecard.html and
    runs `git diff --exit-code` over it, so a single live input — a clock, an
    environment variable, `git rev-parse HEAD` — would make the tracked file
    differ from its own regeneration and the gate would flap forever. Two
    builds from identical inputs must be byte-identical, and the output must
    not contain the repo's current HEAD (the input that used to be there)."""
    import subprocess
    _write_native(tmp_path, NATIVE_TEXTS)
    first = _build_with_webr(tmp_path, WEBR_TIER_ABORTED)
    second = _build_with_webr(tmp_path, WEBR_TIER_ABORTED)
    assert first == second
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=STATS_VALIDATION,
                          capture_output=True, text=True)
    if head.returncode == 0 and head.stdout.strip():
        assert head.stdout.strip()[:12] not in first


def test_webr_honest_cells_with_numbers_phrasing_is_rendered(tmp_path):
    """The '36 cells' fix: the scorecard must say how many of the compared
    cells actually carry a number, in the reader's terms, not just print a
    raw compared-cell count that implies every one is a measurement."""
    payload = dict(WEBR_TIER)
    payload["cells_compared"] = 36
    payload["cells_with_numbers"] = 17
    payload["cells_note"] = "36 = 12 value cells + 7 methods sentences (5 with a number) + 9 term labels + 2 header lines + 6 empty cells."
    html = _build_with_webr(tmp_path, payload)
    assert "<b>36</b>" in html
    assert "<b>17</b>" in html
    assert "carrying a number that could actually drift" in html
    assert "12 value cells" in html   # the note itself is rendered, not dropped


def test_webr_file_without_cells_breakdown_renders_as_before(tmp_path):
    """A webr-tier.json written before this fix (no top-level cells_compared /
    cells_with_numbers) must render exactly as it did before — no crash, no
    fabricated totals paragraph."""
    html = _build_with_webr(tmp_path)   # the original WEBR_TIER fixture
    assert "carrying a number that could actually drift" not in html


def test_every_finding_row_names_the_two_artifacts_it_compared(tmp_path):
    """THE ATTRIBUTION PIN. "Figura" is the screen on the display tier, the
    exported script's harvest on the exact tier, and on the script tier the
    "Python" column is not Path B at all. The shipped logistic-dirty case fails
    its exact tier while its display tier passes — the displayed numbers were
    right and the exported .R was wrong — so a table that labels those rows
    "Figura" alone tells the reader the opposite of what was measured.
    """
    html = _build(tmp_path)
    # The column exists...
    assert "<th>Compared</th>" in html
    # ...and each fixture finding's own source reaches the row.
    assert SRC_EXACT in html          # the exact-tier DEFECT + MISSING_QUANTITY
    assert SRC_SCRIPT in html         # the script-tier SCRIPT_DIVERGENCE
    assert SRC_DISPLAY in html        # the display-tier DECISION_MISMATCH
    # The legend must say what "exported script vs Python" implicates, in the
    # reader's terms, not just print the label.
    assert "export path" in html


def test_a_finding_with_no_source_is_not_silently_attributed(tmp_path):
    """A findings.json written before sources existed (or by a comparator bug)
    must render an em dash, never inherit the column header's implication."""
    fixture = json.loads(json.dumps(FIXTURE))
    del fixture["cases"][1]["findings"][0]["source"]
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(fixture))
    html = build_scorecard.build(findings_path=findings_path,
                                 out_path=tmp_path / "scorecard.html").read_text()
    assert "<td class='source'>&mdash;</td>" in html or \
           "<td class='source'>—</td>" in html


def test_registered_but_uncompared_cases_are_visible(tmp_path):
    """A case can be registered in the Makefile, run its Path A half, and have
    no Path B module yet (summary-table1, until the clean room lands). It is
    absent from findings.json, so without this the scorecard would read "7/7
    cases meet targets" while eight cases were registered — complete-looking
    and wrong. Every registered case appears; the denominator counts it."""
    for case_id in ("case-pass", "case-defect", "case-missing-quantity",
                    "case-decision", "summary-table1"):
        (tmp_path / f"{case_id}.done").write_text("")
    (tmp_path / "summary-table1.figura.json").write_text("{}")

    html = _build(tmp_path)
    assert "summary-table1" in html
    assert "NOT COMPARED" in html
    assert "class='NOT_COMPARED'" in html
    assert ".NOT_COMPARED" in html          # ...and it reaches the CSS
    # The tile denominator now counts five cases, not the four compared.
    assert "<b>2/5</b>" in html
    assert "<b>1</b><span>registered, not compared</span>" in html
    # The row says WHICH half is missing, derived from the artifacts on disk.
    assert "summary-table1.python.json" in html


def test_no_pending_row_or_tile_when_every_registered_case_was_compared(tmp_path):
    for case_id in ("case-pass", "case-defect", "case-missing-quantity",
                    "case-decision"):
        (tmp_path / f"{case_id}.done").write_text("")
    html = _build(tmp_path)
    # The legend explains NOT COMPARED unconditionally; what must be absent is
    # a ROW carrying the state, and the tile.
    assert "class='NOT_COMPARED'" not in html
    assert "registered, not compared</span>" not in html
    assert "<b>2/4</b>" in html


def test_an_absent_findings_file_is_a_clear_error_not_a_stale_scorecard(tmp_path):
    """`make all` deletes findings.json before comparing, so a crash leaves
    none. Publishing the previous run's scorecard would republish stale
    evidence as if it were current; the build stops instead."""
    import pytest
    with pytest.raises(SystemExit) as exc:
        build_scorecard.build(findings_path=tmp_path / "findings.json",
                              out_path=tmp_path / "scorecard.html")
    assert "no findings to publish" in str(exc.value)
    assert not (tmp_path / "scorecard.html").exists()


def test_decision_mismatch_is_styled_and_counted_as_a_defect(tmp_path):
    """Task 11's new code. It must reach the CSS (a row with no styling rule
    renders as ordinary body text, which would make a wrong summary statistic
    look like a passing row) and it must be inside the defects tile, which
    build_scorecard derives from compare.py's DISPOSITIONS rather than from a
    hand-written list."""
    html = _build(tmp_path)
    assert "class='DECISION_MISMATCH'" in html
    assert ".DECISION_MISMATCH" in html
    assert "DECISION_MISMATCH" in build_scorecard.DEFECT_CODES
    # ...and it is explained in the legend, not left as a bare code.
    assert "Decision mismatch" in html


def test_diagnostic_mismatch_is_styled_and_counted_as_a_defect(tmp_path):
    """Task A14's new code, same requirement DECISION_MISMATCH has: reach the
    CSS, reach the defects tile (derived from compare.py's DISPOSITIONS, not
    hand-listed), and be explained in the legend rather than left as a bare
    code."""
    assert "DIAGNOSTIC_MISMATCH" in build_scorecard.DEFECT_CODES
    html = _build(tmp_path)
    assert ".DIAGNOSTIC_MISMATCH" in html
    assert "Diagnostic mismatch" in html


def test_deferred_targets_are_named_in_the_coverage_cell(tmp_path):
    """A target the case declares but this run did not enforce is neither met
    nor failed. Left out of the cell, a case would read "targets met" in green
    while part of its published contract went unexamined."""
    case = {
        "id": "case-deferred",
        "kind": "ratio_table",
        "compared": 35,
        "passed": True,
        "targets_met": True,
        "targets": {"adjusted_or": 4},
        "deferred_targets": ["c_statistic", "vif_note"],
        "findings": [],
    }
    payload = {"cases": [case], "total_compared": 35, "total_findings": 0}
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(payload))
    html = build_scorecard.build(
        findings_path=findings_path,
        out_path=tmp_path / "scorecard.html").read_text()
    assert "2 DEFERRED: c_statistic, vif_note" in html
    assert "targets-deferred" in html
    # ...and the legend says what DEFERRED means.
    assert "<b>DEFERRED</b>" in html


def test_a_case_without_the_deferred_field_renders_as_before(tmp_path):
    """Every case in the main fixture predates `deferred_targets`; none may
    grow a stray marker. The legend's explanation of DEFERRED and the CSS rule
    for it are always present, so the assertion is on the per-case SPAN's class
    ATTRIBUTE — the only thing that could misreport a row."""
    assert "class='targets-deferred'" not in _build(tmp_path)


def test_a_case_with_deferred_targets_does_not_count_toward_the_tile_numerator(tmp_path):
    """Same precedent this file already applies to NOT_COMPARED's denominator
    ("a tile can never read complete while such a case exists"), applied to
    the numerator: a case can carry `targets_met: true` while some of its
    declared targets are DEFERRED (not yet checked at all, per compare.py's
    `_Targets.met`, which is computed only over the non-deferred declared
    targets). Left uncorrected the tile would read "8/8 cases meet targets"
    while 14 declared targets across three real cases were never enforced —
    exactly the misleading combination this test pins against a minimal
    fixture. `test_tile_counts_correct` established the base fixture's
    "2/4"; giving one of those two cases a deferred target must knock it out
    of the numerator without changing the denominator."""
    fixture = json.loads(json.dumps(FIXTURE))
    fixture["cases"][0]["targets_met"] = True
    fixture["cases"][0]["deferred_targets"] = ["c_statistic"]
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(fixture))
    html = build_scorecard.build(
        findings_path=findings_path,
        out_path=tmp_path / "scorecard.html").read_text()
    assert "<b>1/4</b>" in html
    assert "<b>2/4</b>" not in html
    # ...and the label no longer overclaims what the tile counts.
    assert "cases fully meet targets" in html
    # A new tile, mirroring "registered, not compared", makes the excluded
    # case visible rather than just silently smaller.
    assert "<b>1</b><span>cases with deferred targets</span>" in html


def test_no_deferred_cases_tile_when_nothing_is_deferred(tmp_path):
    """The base fixture predates `deferred_targets` entirely, so the new tile
    must not render a stray "0" (or any) tile — mirroring how the pending
    tile is absent when nothing is pending."""
    assert "cases with deferred targets</span>" not in _build(tmp_path)


# ---------------------------------------------------------------------------
# THE PUBLIC PAGE (build_web -> web/validation.html)
#
# Same evidence, a different reader and a different set of ways to be wrong.
# The scorecard is read by someone who can open findings.json; this page is
# read by a clinician deciding whether to trust a number in a manuscript, so
# the tests below are mostly about what it must never quietly assert.
# ---------------------------------------------------------------------------

def _build_web(tmp_path, findings=None, web_dir=None, cases_dir=None) -> str:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(FIXTURE if findings is None else findings))
    out_path = build_scorecard.build_web(
        findings_path=findings_path, out_path=tmp_path / "validation.html",
        web_dir=web_dir, cases_dir=cases_dir)
    return out_path.read_text()


def _plain(fragment: str) -> str:
    """Markup out, whitespace normalised — the sentence as a reader gets it.

    The template is hard-wrapped and carries inline links, so assertions about
    what the page SAYS must not be assertions about where its lines break or
    where an <a> opens."""
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).split())


# An absolute quantifier standing over a noun that means "a number Figura
# shows". The page's own coverage table names things it does NOT compare (the
# hazard-ratio clause of the KM sentence, the prose around the numbers, the
# rendered plots), so any sentence matching this contradicts the table three
# screens below it. "every difference published" is deliberately not caught:
# that one is a promise about disclosure, and it is true.
ABSOLUTE_OVER_NUMBERS = re.compile(
    r"\b(every|all|each|any)\b[^.]{0,40}?\b(number|statistic|quantity|value)s?\b",
    re.I)


def test_web_page_links_the_stylesheet_rather_than_inlining_it(tmp_path):
    """The page ships inside the app. It must ride the app's own tokens, not a
    frozen copy of them — otherwise it drifts the first time styles.css moves,
    and a validation page that looks like a different product is a validation
    page nobody believes.

    So: every colour in the page's own style block is a var(), and the ONLY
    literals live inside the dark remap, which exists precisely to re-point
    those variables (the app ships light-only, so there is nothing upstream to
    read there). Scanned over the whole block rather than its first paragraph —
    a hardcoded `color: #333` anywhere below the fold is the same drift."""
    html = _build_web(tmp_path)
    assert '<link rel="stylesheet" href="styles.css">' in html
    assert "@font-face" not in html          # fonts come from styles.css

    css = html.split("<style>")[1].split("</style>")[0]
    before, marker, after = css.partition("@media (prefers-color-scheme: dark)")
    assert marker, "the dark remap is where the literals are allowed to live"
    outside = before + after.partition("}\n}")[2]
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", outside)
    assert not literals, (
        f"page CSS outside the dark remap must READ the app's tokens, never "
        f"restate a colour: {literals}")


def test_web_page_issues_no_external_request(tmp_path):
    """THE NO-EGRESS INVARIANT, on the one page that could most plausibly want
    an analytics tag. Every href/src must be same-origin and relative, and there
    must be no script at all.

    Built WITH the webR tier present, which is the only build that carries a
    `https://` URL at all: the tier records where it read the runtime version
    from, and that provenance names the module the app loads. It is escaped
    text inside a paragraph — nothing fetches it — and this test is what keeps
    it that way. Against the bare fixture the page renders the "not run"
    branch, contains no URL of any kind, and this test passes by having nothing
    to look at."""
    (tmp_path / "webr-tier.json").write_text(json.dumps(WEBR_TIER))
    html = _build_web(tmp_path)
    assert "https://webr.r-wasm.org/latest/webr.mjs" in html, (
        "the provenance URL must be ON the page for this test to mean anything")
    for attr, value in re.findall(r'(href|src)="([^"]*)"', html):
        assert not value.startswith(("http://", "https://", "//")), \
            f"{attr}={value} leaves the origin"
    assert "<script" not in html
    assert "@import" not in html and "url(" not in html


def test_web_meta_description_qualifies_the_claim_the_page_qualifies(tmp_path):
    """THE ONE PLACE THE CLAIM TRAVELS WITHOUT ITS QUALIFICATIONS.

    Search results and link previews show this string and nothing else — no
    `.claim` block beside it, no coverage table below it. So it carries the
    same two qualifications the page's own lede does: the second implementation
    was built from a WRITTEN SPEC (not blind, not a certification), and the
    comparison is over the fixed cases, not over the reader's own upload."""
    desc = _plain(re.search(r'<meta name="description" content="(.*?)">',
                            _build_web(tmp_path), re.S).group(1))
    assert "independently validated" not in desc
    for overclaim in ("independently written", "independently developed",
                      "independently verified", "independent implementation"):
        assert overclaim not in desc.lower(), (
            f'"{overclaim}" in the meta description drops the qualification '
            f"the page itself makes — the spec was transcribed FROM the R")
    assert "written spec" in desc, "the qualification must travel with the claim"
    assert "every difference published" in desc
    assert "four fixed test datasets" in desc, (
        "the scope is the registered cases, counted, not the reader's file")
    assert not ABSOLUTE_OVER_NUMBERS.search(desc), desc


def test_web_lede_cannot_contradict_the_coverage_table(tmp_path):
    """The lede is read by everyone; the coverage table is read by the diligent.
    They are three screens apart, so the lede is where an absolute claim goes
    unchallenged — and the table underneath it lists, per analysis, exactly what
    the comparison does NOT cover. One of them has to give, and it is not the
    table: it is derived from the cases' own declared targets."""
    html = _build_web(tmp_path)
    assert '<th scope="col">What is not</th>' in html
    assert "the prose wrapped around the numbers" in html   # a real exclusion
    lede = _plain(re.search(r'<p class="lede">(.*?)</p>', html, re.S).group(1))
    assert not ABSOLUTE_OVER_NUMBERS.search(lede), lede
    assert "four fixed test datasets" in lede
    assert "not about a file you upload" in lede

    # ...and on the SHIPPED evidence, where the exclusion the reviewer caught
    # is the KM hazard-ratio clause sitting under "What is not".
    real = json.loads((STATS_VALIDATION / "results" / "findings.json").read_text())
    shipped = _build_web(tmp_path, real, cases_dir=STATS_VALIDATION / "cases")
    assert "the hazard-ratio clause of the displayed sentence" in shipped
    shipped_lede = _plain(
        re.search(r'<p class="lede">(.*?)</p>', shipped, re.S).group(1))
    assert not ABSOLUTE_OVER_NUMBERS.search(shipped_lede), shipped_lede
    assert "eight fixed test datasets" in shipped_lede


def test_web_page_states_the_claim_and_its_limit(tmp_path):
    """The agreed wording, both halves. A page that says only what the harness
    catches is the dishonest half of the sentence."""
    # Prose in the template is hard-wrapped, so assert against a
    # whitespace-normalised copy rather than pinning where the lines break.
    html = " ".join(_build_web(tmp_path).split())
    assert "never read the R" in html
    assert "It cannot catch" in html
    assert "misreading baked into the specification" in html
    # ...and it must not claim a status the project does not have.
    assert "not a medical device" in html
    assert "independently validated" not in html


def test_web_page_publishes_the_findings_rather_than_summarising_them(tmp_path):
    """Every finding, with the comparison named on the row — the tile counts are
    not the evidence, the rows are."""
    html = _build_web(tmp_path)
    assert "Every difference, unabridged" in html
    assert SRC_EXACT in html and SRC_SCRIPT in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html   # escaped, still shown
    assert "9.99" in html


def test_web_export_path_narrative_claims_the_screen_was_right(tmp_path):
    """When every finding on a case is Figura-vs-its-own-exported-script, the
    page may say the displayed numbers were right — that is what the passing
    display tier means."""
    html = _build_web(tmp_path)
    assert "The displayed numbers were right." in html


def test_web_narrative_withdraws_that_claim_when_a_display_finding_exists(tmp_path):
    """THE GUARD ON THE REASSURANCE. `case-decision` carries a screen-vs-Python
    finding, so its block must NOT inherit the export-path story: nothing on the
    page may tell a reader the screen was right about a case where the screen is
    exactly what disagreed."""
    findings = json.loads(json.dumps(FIXTURE))
    findings["cases"] = [c for c in findings["cases"] if c["id"] == "case-decision"]
    findings["total_findings"] = 1
    html = _build_web(tmp_path, findings)
    assert "The displayed numbers were right." not in html
    assert "not all on the export path" in html
    assert SRC_DISPLAY in html


def test_web_download_caveat_is_tied_to_the_findings_that_justify_it(tmp_path):
    """"Run the exported script yourself" carries a caveat only while an
    export-path case is actually publishing findings. When the fix lands and
    they go, the warning goes with them rather than warning about a defect that
    no longer exists."""
    with_findings = _build_web(tmp_path)
    assert "Right now, that first step has a caveat" in with_findings
    # ...and it is written FROM the findings: which cases, how many.
    assert "case-defect, case-missing-quantity" in with_findings
    assert "3 differences are" in with_findings   # 2 + 1 export-path findings

    clean = json.loads(json.dumps(FIXTURE))
    for case in clean["cases"]:
        case["findings"] = []
        case["passed"] = True
    clean["total_findings"] = 0
    html = _build_web(tmp_path, clean)
    assert "Right now, that first step has a caveat" not in html
    assert "Every difference, unabridged" not in html
    # ...and a green page must still refuse to read as "nothing can be wrong".
    assert "A validation page that only ever shows green is not evidence" in html


def test_web_download_caveat_describes_the_findings_it_actually_has(tmp_path):
    """THE DORMANT-PROSE GUARD, and the reason this function is not keyed by
    case id the way CASE_CAUSE and CASE_STATUS are.

    Until 2026-07-28 the caveat carried a paragraph written for `issues/02`:
    R's `read.csv` eating a literal `NA`, "the open defect above", "a fix is
    planned". Its trigger is any export-path finding on ANY case, so that
    paragraph would have republished itself — describing a defect that no
    longer exists, naming a fix that already shipped — the first time an
    unrelated case published an unrelated export-path finding.

    So this test builds exactly that future: one export-path finding, on a
    different case, with a different mechanism. The page must describe THAT
    case and claim nothing about its cause.
    """
    future = json.loads(json.dumps(FIXTURE))
    for case in future["cases"]:
        case["findings"] = []
        case["passed"] = True
    future["cases"].append({
        "id": "km-twoarm",
        "kind": "km_curve",
        "compared": 106,
        "passed": False,
        "targets_met": True,
        "targets": {"median_survival": 2},
        "findings": [{
            "code": "SCRIPT_DIVERGENCE",
            "disposition": "defect",
            "term": "-",
            "quantity": "exported script median",
            "figura": "18.4",
            "python": "18.9",
            "note": "a mechanism that has nothing to do with issues/02",
            "source": SRC_SCRIPT,
        }],
    })
    future["total_findings"] = 1
    html = _build_web(tmp_path, future)

    assert "Right now, that first step has a caveat" in html
    assert "<code>km-twoarm</code>" in html
    assert "1 difference is" in html          # singular, from the count itself
    # The caveat itself, isolated from the standing note beside it (which does
    # legitimately mention read.csv, unconditionally and in the present tense).
    caveat = html.split("Right now, that first step has a caveat")[1]
    caveat = caveat.split("</div>")[0]
    for stale in ("read.csv", "defect", "a fix is planned", "padded",
                  "typed as text", "your data"):
        assert stale not in caveat, (
            f"the caveat claims something findings.json cannot prove: {stale}")
    # ...and no case that is green may be named as carrying a divergence.
    assert "<code>case-defect" not in html


def test_web_page_always_says_a_download_can_differ_from_the_screen(tmp_path):
    """UNCONDITIONAL, and that is the entire point of it.

    The caveat above is generated from findings and disappears with them. But
    the exported script's parity with the app's own parser is maintained, not
    structural, and one export-path divergence is known and open by design
    (`R/km.R`'s numeric-equality branch, which no case here exercises). A page
    that says nothing at all about the download whenever it is green would be
    telling the reader, by silence, that the two cannot differ.

    So the standing sentence must render on a green page, on a red one, and on
    the real shipped evidence — and it must name where the open one is written
    up, since a reader cannot check a claim they cannot find.
    """
    marker = "A standing note on that first step"
    issue = "stats-validation/issues/02-app-vs-exported-script-missing-values.md"

    red = _build_web(tmp_path)
    clean = json.loads(json.dumps(FIXTURE))
    for case in clean["cases"]:
        case["findings"] = []
        case["passed"] = True
    clean["total_findings"] = 0
    green = _build_web(tmp_path, clean)
    real = json.loads((STATS_VALIDATION / "results" / "findings.json").read_text())
    shipped = _build_web(tmp_path, real, cases_dir=STATS_VALIDATION / "cases")

    for name, html in (("red", red), ("green", green), ("shipped", shipped)):
        assert marker in html, f"the standing note is missing on the {name} page"
        assert "Kaplan&ndash;Meier script recodes a numeric status column" in html
        assert issue in html, f"the open divergence is unfindable on {name}"
    # The count it quotes is the page's own case count, not a written-down one.
    assert "all four datasets" in green
    assert "all eight datasets" in shipped


def test_web_page_shows_a_registered_but_uncompared_case(tmp_path):
    """The scorecard's own refusal, on the public page: a case that ran but was
    never compared carries NO guarantee, and must be visible rather than absent
    from a table of green rows."""
    (tmp_path / "orphan.done").touch()
    (tmp_path / "orphan.figura.json").write_text("{}")
    html = _build_web(tmp_path)
    assert "orphan" in html
    assert "never compared" in html
    assert "cases run but never compared" in html


def test_web_every_declared_target_has_a_plain_language_gloss():
    """A target added to compare.py's contract must not reach a published page
    as a bare identifier. This is the only mapping on the page that a reader
    cannot check against the artifact, so it is pinned rather than trusted."""
    from compare import TARGET_QUANTITIES
    missing = set(TARGET_QUANTITIES) - set(build_scorecard.TARGET_GLOSS)
    assert not missing, f"no public gloss for {sorted(missing)}"


def test_web_coverage_table_separates_precision_tiers(tmp_path):
    """Full-precision agreement and as-displayed agreement are different
    claims, and the page must not let the stronger one cover the weaker."""
    html = _build_web(tmp_path)
    assert "At full precision" in html
    assert "As displayed" in html
    assert "The downloaded script" in html
    assert "What is not" in html


def test_web_page_is_a_pure_function_of_its_inputs(tmp_path):
    """Same precondition the scorecard has: CI byte-diffs the published page, so
    a clock or a HEAD lookup would make the gate flap forever."""
    import subprocess
    first = _build_web(tmp_path)
    second = _build_web(tmp_path)
    assert first == second
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=STATS_VALIDATION,
                          capture_output=True, text=True)
    if head.returncode == 0 and head.stdout.strip():
        assert head.stdout.strip()[:12] not in first


def test_web_page_renders_in_dark_as_well_as_light(tmp_path):
    """The app ships light-only and styles.css is not this page's to edit, so
    the dark scheme is a remap of the SAME token names in the page's own style
    block. Without it the page renders warm-paper-on-white inside a dark OS."""
    html = _build_web(tmp_path)
    assert "@media (prefers-color-scheme: dark)" in html
    dark = html.split("@media (prefers-color-scheme: dark)")[1].split("}\n}")[0]
    for token in ("--ink:", "--panel:", "--chrome:", "--accent:", "--error:"):
        assert token in dark, f"{token} is not remapped for dark"


def test_web_webr_section_states_its_coverage_ratio(tmp_path):
    """Two green rows without "2 of 8" reads as whole-roster parity."""
    (tmp_path / "cox-adjusted.done").touch()
    (tmp_path / "logistic-confounding.done").touch()
    (tmp_path / "km-twoarm.done").touch()
    (tmp_path / "webr-tier.json").write_text(json.dumps(WEBR_TIER))
    html = _build_web(tmp_path)
    assert "Coverage: 2 of 3 cases." in html
    assert "not</i> covered by any wasm-vs-native claim" in html


def test_web_webr_empty_state_is_not_a_pass(tmp_path):
    """No webr-tier.json means the gate was not run for this release. The page
    must say so rather than omitting the section, which reads as "nothing to
    report"."""
    html = _build_web(tmp_path)
    assert "has not been run for the current release" in html


def test_web_webr_staleness_is_reported_to_the_reader(tmp_path):
    """The digests the scorecard checks are checked here too: published webR
    evidence measured against an older app must say so on the page a user
    reads, not only on the maintainer's scorecard."""
    payload = dict(WEBR_TIER)
    payload["web_digest"] = "sha256:not-the-real-tree"
    (tmp_path / "webr-tier.json").write_text(json.dumps(payload))
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "app.js").write_text("// something")
    html = _build_web(tmp_path, web_dir=web_dir)
    assert "The shipped app has changed since this evidence was measured" in html


def test_web_case_analysis_names_come_from_the_case_files(tmp_path):
    """Grouping by analysis is read from each case's own case.json `figure`,
    never guessed from the id — and an unreadable case file says so instead of
    being filed under whatever analysis sorts first."""
    cases_dir = tmp_path / "cases"
    (cases_dir / "case-pass").mkdir(parents=True)
    (cases_dir / "case-pass" / "case.json").write_text(json.dumps({"figure": "cox"}))
    html = _build_web(tmp_path, cases_dir=cases_dir)
    assert "Cox regression" in html
    assert "unknown (case.json unreadable)" in html


def test_web_page_drops_the_defect_disclosure_once_the_real_case_is_green(tmp_path):
    """The real shipped evidence, post-fix.

    This test used to assert the opposite: while `logistic-dirty` published 30
    findings, the page had to name the defect as known, tracked and being fixed,
    or it read as an unattended failure. `issues/02` was fixed on 2026-07-28 and
    that case now publishes nothing, so the assertion inverts — and the thing it
    really pins is that the disclosure was written to REMOVE ITSELF. Every
    paragraph of it (the narrative block, the download caveat, the unabridged
    table) was keyed to findings existing, which is what made it safe to publish
    prose about a defect in a generated page in the first place.

    The `total_findings == 0` guard is deliberate: if the real evidence ever
    publishes again, this test fails loudly with instructions rather than
    silently checking the wrong branch.
    """
    real = json.loads((STATS_VALIDATION / "results" / "findings.json").read_text())
    assert real["total_findings"] == 0, (
        "the real findings.json publishes again — restore a CASE_STATUS entry "
        "for the failing case in build_scorecard.py and assert on it here, the "
        "way this test did before issues/02 was fixed")
    html = _build_web(tmp_path, real, cases_dir=STATS_VALIDATION / "cases")
    assert "This is a known defect, and it is open." not in html
    assert "Right now, that first step has a caveat" not in html
    assert "Every difference, unabridged" not in html
    # ...and the green page still refuses to read as "nothing can be wrong".
    assert "No case currently publishes a difference" in html
    assert "A validation page that only ever shows green is not evidence" in html
    assert "Logistic regression" in html


def test_web_page_admits_when_a_failing_case_has_no_recorded_disposition(tmp_path):
    """CASE_STATUS is empty today: its only entry was deleted with the fix that
    made `logistic-dirty` green, rather than left dormant where nobody would
    re-read it before the day it rendered again.

    So a case that publishes export-path findings with no entry must SAY the
    page cannot speak to whether they are being worked on — never inherit
    another case's status, and never imply someone is on it. That sentence is
    also the prompt to write the missing entry.
    """
    html = _build_web(tmp_path)
    assert "no recorded disposition" in html
    assert "This is a known defect, and it is open." not in html
