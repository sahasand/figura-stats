"""findings.json -> a scorecard for maintainers, and the public page for users.

Two outputs, one evidence file, no live computation:

  * `results/scorecard.html` — the internal scorecard (self-contained, opens
    from `file://`), written by `build()`.
  * `web/validation.html` — the page a clinical user reads, written by
    `build_web()`. It is part of the shipped app: it LINKS `web/styles.css`
    rather than inlining CSS, so it cannot drift from the design tokens.

    $ python build_scorecard.py          # both
    $ python build_scorecard.py --web    # the public page only

Reads the exact shape compare.py's `main()` writes (verified against
stats-validation/compare/compare.py and a real stats-validation/results/
findings.json):

  {cases: [{id, kind, compared, passed, targets_met, targets: {...},
            findings: [{code, disposition, term, quantity, figura, python,
                        note, source}, ...]}, ...],
   total_compared, total_findings}

TWO THINGS THIS FILE REFUSES TO LET THE READER ASSUME.

1. `figura` is not one artifact. On the display tier it is the SCREEN; on the
   exact tier it is the harvest from re-running the EXPORTED SCRIPT; on the
   script tier the `python` column is the exported script rather than Path B.
   compare.py stamps every finding with a `source` naming the comparison, and
   the table prints it in its own column — because the shipped logistic-dirty
   case USED to fail its exact tier while its display tier passed, i.e. the
   numbers on screen were right and the exported .R was wrong, and a column
   headed "Figura" alone says the opposite. (That case is green as of the
   .script_data fix, issues/02; the distinction it taught this file is not, and
   the next export-path finding will need the column just as badly.)
2. findings.json only lists cases that were COMPARED. A case can be registered
   in the Makefile, run its Path A half, and still have no second opinion (no
   python.json). Those cases get their own visibly-incomplete rows here, from
   the artifacts on disk in results/ — otherwise a scorecard reading "7/7"
   while eight cases are registered looks complete when it is not.

There is no top-level `targets` key — only per-case. Findings never carry
`code == "PASS"` (compare.py only appends non-pass findings; a passing case
has an empty `findings` list) and the taxonomy has no `EXACT_PASS` — that
code was considered and never wired to any emission (see compare.py's
DISPOSITIONS comment), so it is not styled here. The REAL emitted codes are:
PASS (synthesised here for a no-findings case row), DISPLAY_ARTIFACT, DEFECT,
COUNT_MISMATCH, DECISION_MISMATCH, DIAGNOSTIC_MISMATCH, SCRIPT_DIVERGENCE,
MISSING_QUANTITY.

Each case may also carry `deferred_targets` — declared coverage whose
comparison block has not landed yet. It is rendered inside the Coverage cell,
never silently dropped into "targets met".
"""
from __future__ import annotations

import hashlib
import html
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
# The shipped app tree the webR tier drives, digested for the `web/`-staleness
# note. Phase 1 never EDITS web/; this only reads it.
WEB = Path(__file__).resolve().parent.parent / "web"

# THIS MODULE READS NO LIVE STATE. Every byte it writes is a function of FILES
# ON DISK and of the code here — no clock, no environment, no `git rev-parse`.
# That is not tidiness, it is the precondition for the freshness gate to exist at
# all: CI rebuilds scorecard.html and runs `git diff --exit-code` over it, so any
# live input would make the tracked artifact differ from its own regeneration and
# the gate would flap forever.
#
# "Files on disk" is deliberately wider than "results/": the webR staleness notes
# also digest results/<id>.figura.json and the tracked sources under web/. Both
# are checked-out repo content, identical in CI and locally at the same commit,
# so the determinism property holds — what it excludes is state that is NOT a
# function of the tree (the clock, the environment, HEAD).
#
# It used to read live HEAD, for the webR staleness note, and that was exactly
# the bug: committing the scorecard advances HEAD, so the note in the committed
# file named the PREVIOUS commit and could never again match a rebuild. (Real
# instance: the file tracked at 93aa973 said "HEAD is now 2997e1b1f9b0".) The
# note now derives from `native_digest` instead — see _stale_native_digest.

# DISPOSITIONS comes from compare.py itself, not a restated copy, so the
# "defects" tile and compare.py's own finding taxonomy can never drift apart
# (this was a real bug: a hand-picked DEFECT_CODES tuple here once omitted
# MISSING_QUANTITY, which DISPOSITIONS classifies as a "defect" and the CSS
# below styles identically red/bold — a MISSING_QUANTITY finding rendered a
# red row while the tile claimed zero defects). compare/ is a sibling
# directory, not a package (no __init__.py), so it needs a sys.path shim of
# its own — mirroring the shim compare/tests/test_scorecard.py already uses
# in the other direction to import this module.
COMPARE_DIR = Path(__file__).resolve().parent / "compare"
sys.path.insert(0, str(COMPARE_DIR))

from compare import (  # noqa: E402
    DISPOSITIONS, PUBLISHED_SIGNIFICANT_DIGITS, REL_TOL, SRC_COVERAGE,
    SRC_DISPLAY, SRC_EXACT, SRC_HARVEST, SRC_PATH_B, SRC_SCREEN, SRC_SCRIPT,
)

CSS = """
:root { --ink:#1a1a1a; --muted:#5b5b5b; --rule:#d8d4cc; --paper:#faf8f5;
        --pass:#0d6b63; --warn:#8a6d1f; --fail:#a02c2c; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#ececec; --muted:#a5a5a5; --rule:#3a3a3a; --paper:#16181a; } }
:root[data-theme="dark"] { --ink:#ececec; --muted:#a5a5a5; --rule:#3a3a3a; --paper:#16181a; }
:root[data-theme="light"] { --ink:#1a1a1a; --muted:#5b5b5b; --rule:#d8d4cc; --paper:#faf8f5; }
body { margin:0; padding:2.5rem 1.25rem; background:var(--paper); color:var(--ink);
       font:16px/1.6 "IBM Plex Sans", system-ui, sans-serif; }
main { max-width:64rem; margin:0 auto; }
h1 { font:600 1.6rem/1.2 "Source Serif 4", Georgia, serif; margin:0 0 .25rem; }
h2 { font:600 1.15rem/1.2 "Source Serif 4", Georgia, serif; margin:2rem 0 .5rem; }
.sub { color:var(--muted); margin:0 0 2rem; }
.tiles { display:flex; flex-wrap:wrap; gap:1rem; margin-bottom:2rem; }
.tile { border:1px solid var(--rule); border-radius:8px; padding:.9rem 1.1rem;
        min-width:9rem; }
.tile b { display:block; font:600 1.5rem/1 "IBM Plex Mono", monospace; }
.tile span { color:var(--muted); font-size:.8rem; text-transform:uppercase;
             letter-spacing:.04em; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:.9rem; }
th,td { text-align:left; padding:.45rem .6rem; border-bottom:1px solid var(--rule);
        vertical-align:top; }
th { font-weight:600; }
code { font:.85em "IBM Plex Mono", monospace; word-break:break-word; }
/* Real emitted finding codes only (compare.py DISPOSITIONS). No EXACT_PASS:
   the comparator never emits it, so styling it would suggest a tier ran that
   did not. NOT_COMPARED is the one class here that is NOT a compare.py code —
   it is this file's own state for a registered case findings.json never
   mentions, and it is styled warn rather than fail because nothing failed:
   nothing was checked. */
.PASS { color:var(--pass); }
.DISPLAY_ARTIFACT { color:var(--warn); }
.DEFECT,.COUNT_MISMATCH,.SCRIPT_DIVERGENCE,.MISSING_QUANTITY,
.DECISION_MISMATCH,.DIAGNOSTIC_MISMATCH { color:var(--fail); font-weight:600; }
.NOT_COMPARED { color:var(--warn); font-weight:600; }
.targets-met { color:var(--pass); font-size:.78rem; white-space:nowrap; }
.targets-unmet { color:var(--fail); font-weight:600; font-size:.78rem; white-space:nowrap; }
.targets-none { color:var(--warn); font-weight:600; font-size:.78rem; white-space:nowrap; }
.targets-deferred { color:var(--warn); font-weight:600; font-size:.78rem; }
.source { color:var(--muted); font-size:.78rem; white-space:nowrap; }
.webr-empty { border:1px dashed var(--rule); border-radius:8px; padding:1rem 1.1rem;
              color:var(--muted); }
/* A drifting case must not read like a passing one at a glance. IDENTICAL is
   the pass colour and normal weight; DRIFT is the fail colour and bold, same
   treatment the defect codes above get, and its rows carry the differing
   values so the reader sees the size of the drift, not just its existence.
   ABORTED (the case threw before it finished a comparison — a structural
   precondition failure such as a row-count mismatch, but also any other
   check `runCase` wraps) gets the same fail colour and weight as DRIFT — it
   is not a lesser problem, it is the harness saying this case produced no
   comparison at all — but italic, so it is never mistaken for a DRIFT
   verdict at a glance. */
.webr-identical { color:var(--pass); }
.webr-drift { color:var(--fail); font-weight:600; }
.webr-aborted { color:var(--fail); font-weight:600; font-style:italic; }
.webr-runtime { color:var(--muted); font-size:.85rem; margin:0 0 1rem; }
.webr-totals { margin:0 0 1rem; }
/* The staleness note: turns "the native numbers moved under this evidence"
   from a silent wrong claim into visible information (see
   _stale_native_digest's docstring). Same warn colour as
   .DISPLAY_ARTIFACT/.NOT_COMPARED above, not fail — an out-of-date gate is a
   thing to notice, not a defect the gate itself found. */
.webr-stale { color:var(--warn); font-size:.85rem; margin:0 0 1rem; }
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


# Every code whose disposition is "defect" per compare.py's own vocabulary —
# currently DEFECT, COUNT_MISMATCH, SCRIPT_DIVERGENCE, and MISSING_QUANTITY —
# derived, not hand-listed, so a future code compare.py adds under "defect"
# is counted here automatically instead of silently undercounting.
DEFECT_CODES = frozenset(
    code for code, disposition in DISPOSITIONS.items() if disposition == "defect"
)


def registered_cases(results_dir: Path) -> list[str]:
    """Every case the pipeline actually RAN, read off results/.

    The Makefile touches `results/<id>.done` per case — including cases that
    only have a Path A half — so the marker files are the case list. The
    `.figura.json` artifacts are unioned in as a fallback for a results/ that
    was populated without the marker (e.g. a hand-run harness step).
    """
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        return []
    ids = {p.name[: -len(".done")] for p in results_dir.glob("*.done")}
    ids |= {p.name[: -len(".figura.json")]
            for p in results_dir.glob("*.figura.json")}
    return sorted(ids)


def _pending(data: dict, results_dir: Path) -> list[str]:
    """Registered cases that findings.json does not account for."""
    compared = {c["id"] for c in data["cases"]}
    return [c for c in registered_cases(results_dir) if c not in compared]


def _tiles(data: dict, pending: list[str]) -> str:
    compared = data["total_compared"]
    findings = data["total_findings"]
    defects = sum(
        1 for c in data["cases"] for f in c["findings"]
        if f["code"] in DEFECT_CODES
    )
    cases = data["cases"]
    # A case whose `targets_met` is True can still carry non-empty
    # `deferred_targets` — that field is deliberately excluded from the `met`
    # computation itself (a deferred target is neither met nor failed), so
    # `targets_met: true` alone does not mean every declared target was
    # checked. Applying the SAME PRECEDENT this file already applies to
    # NOT_COMPARED ("a tile can never read complete while such a case
    # exists"): a case with any deferred target does not count toward the
    # numerator here either, and the label says "fully" so the tile cannot be
    # read as a stronger claim than it is.
    met = sum(
        1 for c in cases if c["targets_met"] and not c.get("deferred_targets"))
    deferred_cases = sum(1 for c in cases if c.get("deferred_targets"))
    # DENOMINATOR IS EVERY REGISTERED CASE, not just the compared ones: a tile
    # reading "7/7" while an eighth case sits uncompared is a true statement
    # that reads as a false one.
    total = len(cases) + len(pending)
    pending_tile = (
        f"\n  <div class=\"tile\"><b>{len(pending)}</b>"
        f"<span>registered, not compared</span></div>" if pending else "")
    deferred_tile = (
        f"\n  <div class=\"tile\"><b>{deferred_cases}</b>"
        f"<span>cases with deferred targets</span></div>" if deferred_cases else "")
    return f"""<div class="tiles">
  <div class="tile"><b>{esc(compared)}</b><span>values compared</span></div>
  <div class="tile"><b>{esc(findings)}</b><span>differences</span></div>
  <div class="tile"><b>{esc(defects)}</b><span>defects</span></div>
  <div class="tile"><b>{met}/{total}</b><span>cases fully meet targets</span></div>{deferred_tile}{pending_tile}
</div>"""


def _pending_rows(pending: list[str], results_dir: Path) -> str:
    """A visible row per registered-but-uncompared case, saying which half is
    missing — read from the artifacts on disk, never hard-coded to one case."""
    rows = []
    for case_id in pending:
        have_a = (results_dir / f"{case_id}.figura.json").exists()
        have_b = (results_dir / f"{case_id}.python.json").exists()
        if have_a and not have_b:
            why = ("Path A artifacts published; no Path B artifact "
                   f"({case_id}.python.json) exists, so nothing was compared "
                   "and this case is covered by no guarantee")
        elif not have_a:
            why = ("no Path A artifact "
                   f"({case_id}.figura.json); the case did not run")
        else:
            why = ("both paths produced artifacts but the case was not passed "
                   "to the comparator")
        rows.append(
            f"<tr><td>{esc(case_id)}</td>"
            f"<td class='NOT_COMPARED'>NOT COMPARED</td>"
            f"<td class='targets-none'>NO COVERAGE</td>"
            f"<td class='source'>&mdash;</td>"
            f"<td colspan='4'>{esc(why)}</td></tr>")
    return "".join(rows)


def _coverage_cell(case: dict) -> str:
    """The Coverage cell, including any DEFERRED targets.

    A deferred target is one the case declares and this run did not enforce
    because its comparison block has not landed yet (compare.py's
    PENDING_PATH_B_DIAGNOSTICS). It is neither met nor failed — it was not
    checked — so it is named in the cell rather than folded into either verdict.
    Without this a case reads "targets met" in green while part of its published
    contract went unexamined, which is the one thing this scorecard exists not
    to do. `.get` keeps an older findings.json, written before the field
    existed, rendering exactly as it used to.
    """
    targets_class = "targets-met" if case["targets_met"] else "targets-unmet"
    targets_label = "targets met" if case["targets_met"] else "TARGETS UNMET"
    deferred = case.get("deferred_targets") or []
    extra = ""
    if deferred:
        extra = (f"<br><span class='targets-deferred'>{len(deferred)} DEFERRED:"
                 f" {esc(', '.join(deferred))}</span>")
    return f"<td class='{targets_class}'>{esc(targets_label)}{extra}</td>"


def _rows(data: dict) -> str:
    rows = []
    for c in data["cases"]:
        coverage_cell = _coverage_cell(c)
        if not c["findings"]:
            rows.append(
                f"<tr><td>{esc(c['id'])}</td><td class='PASS'>PASS</td>"
                f"{coverage_cell}<td class='source'>&mdash;</td>"
                f"<td colspan='4'>{esc(c['compared'])} values compared, "
                f"no differences</td></tr>"
            )
            continue
        for f in c["findings"]:
            # `source` names which two artifacts the two value columns hold.
            # Older findings.json files predate it; they render an em dash
            # rather than an unlabelled (and therefore misattributed) row.
            rows.append(
                f"<tr><td>{esc(c['id'])}</td>"
                f"<td class='{esc(f['code'])}'>{esc(f['code'])}</td>"
                f"{coverage_cell}"
                f"<td class='source'>{esc(f.get('source') or '—')}</td>"
                f"<td>{esc(f['term'])}</td><td>{esc(f['quantity'])}</td>"
                f"<td><code>{esc(f['figura'])}</code></td>"
                f"<td><code>{esc(f['python'])}</code></td></tr>"
            )
    return "".join(rows)


def _native_digest(results_dir: Path, case_ids: list[str]) -> str | None:
    """Recompute webr-tier.json's `native_digest` from the artifacts on disk.

    A byte-for-byte mirror of `nativeDigest` in e2e/compare-text.mjs: sha256
    over `id + " " + text + " "` for each case, ids sorted, `text` being the
    native-R display string in results/<id>.figura.json — the exact strings the
    webR run compared against.

    Returns None (never a fabricated digest) when any input is missing, so a
    scorecard built without the pipeline's intermediates says nothing rather
    than claiming staleness it cannot demonstrate.
    """
    if not all(isinstance(case_id, str) for case_id in case_ids):
        return None
    digest = hashlib.sha256()
    for case_id in sorted(case_ids):
        path = results_dir / f"{case_id}.figura.json"
        if not path.exists():
            return None
        try:
            text = json.loads(path.read_text()).get("text")
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(text, str):
            return None
        digest.update(case_id.encode("utf-8"))
        digest.update(b" ")
        digest.update(text.encode("utf-8"))
        digest.update(b" ")
    return f"sha256:{digest.hexdigest()}"


def _is_web_source(rel_path: str) -> bool:
    """A byte-for-byte mirror of `isWebSource` in e2e/compare-text.mjs.

    Kept as a restatement rather than a shared file because the two live in
    different languages; `test_web_digest_matches_the_javascript_implementation`
    runs both and compares the digests, so a drift between them fails a test
    instead of silently producing a permanent false staleness note.
    """
    if rel_path.startswith("R/") or rel_path.startswith("webr/"):
        return False
    if rel_path.endswith(".test.mjs"):
        return False
    return (rel_path.endswith(".js") or rel_path == "index.html"
            or rel_path == "styles.css")


def _web_digest(web_dir: Path) -> str | None:
    """Recompute webr-tier.json's `web_digest` from the shipped app sources.

    Mirror of `webDigest` in e2e/compare-text.mjs: sha256 over
    `relpath + NUL + bytes + NUL` for every included file, paths sorted by CODE
    POINT (Python's `sorted()`; the JS side deliberately uses `<` rather than
    `localeCompare` for exactly this reason — see that function's comment).

    Returns None when web/ is not there at all, so a checkout without it says
    nothing rather than claiming staleness it cannot demonstrate.
    """
    web_dir = Path(web_dir)
    if not web_dir.is_dir():
        return None
    paths = sorted(
        p.relative_to(web_dir).as_posix() for p in web_dir.rglob("*")
        if p.is_file() and _is_web_source(p.relative_to(web_dir).as_posix()))
    if not paths:
        return None
    digest = hashlib.sha256()
    for rel in paths:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update((web_dir / rel).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _stale_web_digest(raw: dict, web_dir: Path) -> str | None:
    """The recomputed `web/` digest when it DISAGREES with the recorded one.

    THE STALENESS DIRECTION `native_digest` CANNOT SEE. A change under `web/`
    can move what the browser computes or displays while every native-R artifact
    stays byte-identical — so the native digest still agrees and the page would
    keep claiming parity for an app the browser was never driven against. This
    was a knowingly-open gap, documented in prose; it is now measured.

    Absent field (any webr-tier.json written before the field existed) renders
    nothing, exactly as it used to. Never fabricates a digest.
    """
    recorded = raw.get("web_digest")
    if not recorded:
        return None
    recomputed = _web_digest(web_dir)
    if recomputed is None or recomputed == recorded:
        return None
    return recomputed


def _stale_native_digest(raw: dict, results_dir: Path,
                         case_ids: list[str]) -> str | None:
    """The recomputed digest when it DISAGREES with the recorded one, else None.

    THE GUARD, deterministically. The thing that actually makes published webR
    evidence stale is the native output moving underneath it — a later
    `make all` changing results/<id>.figura.json's `text` — and webr-tier.json
    already records a digest of exactly those strings for exactly this purpose
    (see the comment above `digestInput` in e2e/webr-parity.spec.js). So the
    staleness question is answerable from the artifacts alone.

    This replaces a live `git rev-parse HEAD` comparison, and is strictly
    better on both counts that matter:

      * DETERMINISM. Same inputs, same HTML, on any machine at any commit. The
        HEAD version could not survive its own commit (see the module header),
        which made the tracked scorecard permanently un-regenerable.
      * WHAT IT CATCHES. The regression this guard was written for was a patch
        script re-deriving `commit` from HEAD and clobbering the true value.
        A HEAD comparison is DEFEATED by that clobber — the two now agree, so
        no note renders. The digest is not: clobbering `commit` does not touch
        `native_digest`, so moved native output still says so on the page.

    What it gives up: "HEAD has moved at all" — which fired on every commit
    including the one publishing the scorecard, so it was noise, not signal. The
    one USEFUL thing that crude check covered and this does not — a change under
    web/ that moves webR behaviour while native R output stays put — is covered
    by `_stale_web_digest` below. It used to be a documented gap; it is now a
    measurement.
    """
    recorded = raw.get("native_digest")
    if not recorded:
        return None
    recomputed = _native_digest(results_dir, case_ids)
    if recomputed is None or recomputed == recorded:
        return None
    return recomputed


def _webr_section(results_dir: Path, web_dir: Path | None = None) -> str:
    """The webR-vs-native-R release gate, read from results/webr-tier.json.

    That file is written ONLY by a real browser run of
    stats-validation/e2e/webr-parity.spec.js (a hand-run gate — it needs a
    browser and the network, so it is in neither `make all` nor CI). It is
    deleted at the start of every run, so an absent file means "this release
    has not been gated", never "the last run's numbers still apply". Say that
    plainly rather than fabricating a result or crashing.

    A DRIFT case is styled like a defect, not like a footnote: the whole point
    of the tier is that a wasm-vs-native difference in a shipped number is a
    finding, and a reader skimming the section must not mistake one for a pass.

    An ABORTED case (anything `e2e/compare-text.mjs`'s `runCase` caught before
    the case finished a comparison) is rendered as its own distinct verdict,
    never silently absent. Before this existed, such a failure aborted the
    whole spec before webr-tier.json was ever written, so the single most
    alarming drift class — the two runtimes disagreeing on the SHAPE of the
    output — rendered identically to "never run" (the empty-state branch
    above). Distinguishing the two is the entire point of this branch.

    THE DETAIL TEXT NAMES NO CAUSE, deliberately. It used to assert "the two
    runtimes disagreed on the shape of the output before any cell was
    compared", which was true when the only wrapped throw sites were the
    structural preconditions. `runCase` now also wraps the driver's own
    cross-checks (case.json's figure vs this file's driver, an unregistered
    display kind, "cox has no increment control in the UI", "<column> is not
    in the variable checklist"), so that sentence would now often be a
    fabricated diagnosis printed over the top of a `reason` that says
    otherwise. The reason is rendered verbatim; the framing around it is
    neutral.

    AN ABORTED CASE IS NOT COVERAGE. It is excluded from `covered` below, so
    the coverage prose routes into its partial branch and NAMES it as
    ungated. This matters because webr-tier.json is written BEFORE the run
    fails loudly, and `make all` re-renders from whatever is on disk: without
    the exclusion, a page could print "Coverage: 8 of 8 cases … every
    registered case is driven through the shipped browser UI" directly above
    an ABORTED row.
    """
    path = results_dir / "webr-tier.json"
    if not path.exists():
        return (
            "<div class=\"webr-empty\">Not yet run for this release &mdash; "
            "run <code>make -C stats-validation webr</code> (a hand-run "
            "release gate: it needs a browser and the network, so it is "
            "excluded from CI and from <code>make all</code>).</div>"
        )
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return (
            "<div class=\"webr-empty\">webr-tier.json is present but could "
            "not be read as JSON.</div>"
        )

    cases = raw.get("cases") or []
    rows = []
    for c in cases:
        if c.get("aborted"):
            rows.append(
                f"<tr><td>{esc(c.get('id'))}</td>"
                f"<td class='webr-aborted'>ABORTED</td>"
                f"<td>&mdash;</td>"
                f"<td>The run did not complete a comparison for this case: "
                f"{esc(c.get('reason'))}</td></tr>")
            continue
        identical = bool(c.get("identical"))
        cls = "webr-identical" if identical else "webr-drift"
        label = "IDENTICAL" if identical else "DRIFT"
        differing = c.get("differing_cells") or []
        compared = c.get("cells_compared")
        if identical:
            # SAME VOCABULARY AS THE PUBLIC PAGE, and no count here. "Cells"
            # was the ratio-table era's noun; five of the eight cases display
            # sentences, not cells, so `groupcompare-categorical` read "1
            # displayed cells matched" — the wrong noun AND a plural bug on
            # the one case small enough to expose it. The count lives in the
            # adjacent "Strings compared" column, so dropping it from the
            # sentence removes the pluralisation problem rather than papering
            # over it.
            detail = "every displayed string matched native R exactly"
        else:
            items = "".join(
                f"<li><b>{esc(d.get('term'))}</b> / {esc(d.get('column'))}: "
                f"native <code>{esc(d.get('native'))}</code> &rarr; "
                f"webR <code>{esc(d.get('webr'))}</code></li>"
                for d in differing)
            n = len(differing)
            detail = (f"{n} of {esc(compared)} string"
                      f"{'' if n == 1 else 's'} differ{'s' if n == 1 else ''}"
                      f"<ul>{items}</ul>")
        rows.append(
            f"<tr><td>{esc(c.get('id'))}</td>"
            f"<td class='{cls}'>{label}</td>"
            f"<td>{esc(compared)}</td>"
            f"<td>{detail}</td></tr>")

    if not rows:
        rows.append("<tr><td colspan='4'>webr-tier.json lists no cases.</td>"
                    "</tr>")

    # `runtime_source` is optional provenance: the page prints no version
    # string, so the tier records HOW it identified the runtime. Rendered when
    # present so the runtime line can never be read as an unsourced claim.
    source = raw.get("runtime_source")
    source_html = f"<br>{esc(source)}" if source else ""
    # `commit` binds this evidence to the repo state it was measured against
    # (finding: "the artifact binds to no app version/native baseline"). Shown
    # short (12 hex chars, same convention as `git rev-parse --short`) but the
    # field itself stores the full hash.
    commit = raw.get("commit")
    commit_html = (f" &middot; commit <code>{esc(str(commit)[:12])}</code>"
                    if commit else "")
    header_html = (
        f"<p class=\"webr-runtime\">Runtime: <code>"
        f"{esc(raw.get('runtime'))}</code> &middot; run "
        f"{esc(raw.get('date'))}{commit_html}{source_html}</p>"
    )

    # THE GUARD (fix for a real regression — see repoCommit()'s docstring in
    # e2e/webr-parity.spec.js): a later `make all` that changes native output,
    # OR an offline edit to webr-tier.json that clobbers `commit` outright,
    # must never be able to leave this evidence silently claiming parity with
    # numbers the browser was not actually run against. Rather than relying on
    # a reader to check by hand, say it on the page — from the artifacts, not
    # from live git, so the rendered file stays a pure function of its inputs
    # (see _stale_native_digest for the full argument). Digests equal, or not
    # computable, renders nothing extra: additive information, never a
    # fabricated claim.
    staleness_html = ""
    stale_digest = _stale_native_digest(
        raw, results_dir, [c.get("id") for c in cases if not c.get("aborted")])
    if stale_digest:
        staleness_html = (
            f"<p class=\"webr-stale\">Gate last run against native output "
            f"digesting to <code>{esc(str(raw.get('native_digest'))[:19])}"
            f"&hellip;</code>; the native display artifacts in "
            f"<code>results/</code> now digest to "
            f"<code>{esc(stale_digest[:19])}&hellip;</code> &mdash; the native "
            f"numbers this evidence was compared against have changed since it "
            f"ran. Re-run <code>make -C stats-validation webr</code>.</p>"
        )
    # The other direction, and a SEPARATE note rather than a shared one: "the
    # native numbers moved" and "the app moved" are different facts with
    # different remedies, and collapsing them into one sentence would leave a
    # reader unable to tell which happened.
    stale_web = _stale_web_digest(raw, web_dir if web_dir is not None else WEB)
    if stale_web:
        staleness_html += (
            f"<p class=\"webr-stale\">Gate last run against app sources "
            f"digesting to <code>{esc(str(raw.get('web_digest'))[:19])}"
            f"&hellip;</code>; <code>web/</code> now digests to "
            f"<code>{esc(stale_web[:19])}&hellip;</code> &mdash; the shipped "
            f"app has changed since this evidence was measured, so it describes "
            f"a browser run of an older tree. Re-run "
            f"<code>make -C stats-validation webr</code>.</p>"
        )

    # The honest "36 cells" fix: not every compared cell is a number that
    # could drift (most are static labels, headers, and intentionally-blank
    # placeholder cells). When the run recorded the breakdown, say so in the
    # reader's terms instead of leaving "N cells compared" to imply N
    # measurements. Older webr-tier.json files (pre-fix) lack these top-level
    # fields and render exactly as before — no crash, no fabricated numbers.
    total_compared = raw.get("cells_compared")
    total_with_numbers = raw.get("cells_with_numbers")
    totals_html = ""
    if total_compared is not None and total_with_numbers is not None:
        note = raw.get("cells_note")
        note_html = f"<br>{esc(note)}" if note else ""
        totals_html = (
            f"<p class=\"webr-totals\">Compared every one of the "
            f"<b>{esc(total_compared)}</b> strings the app displays across "
            f"these cases &mdash; <b>{esc(total_with_numbers)}</b> of them "
            f"carrying a number that could actually drift between native R "
            f"and webR.{note_html}</p>"
        )

    # COVERAGE, ON THE PAGE AND NOT ONLY IN THE README. A section that lists
    # green rows without saying how much of the roster they are reads as
    # whole-roster parity. Both numbers are read off files on disk (the tier's
    # own case list, and results/ for the registered roster), so this stays a
    # pure function of its inputs like everything else here — and the ratio
    # keeps being stated even now that it is 8 of 8, because "all of them" is a
    # claim a reader is entitled to see counted rather than asserted.
    #
    # AN ABORTED CASE IS NOT COVERED — it produced no comparison at all, so
    # counting it here would let the section print "8 of 8 … every registered
    # case is driven through the shipped browser UI" one line above an ABORTED
    # row. Excluding it routes the prose into the partial branch, which names
    # the case as ungated. Reachable in practice, not theoretically: the spec
    # writes webr-tier.json BEFORE it fails loudly, and `make all` re-renders
    # from whatever is on disk.
    registered = registered_cases(results_dir)
    covered = [c.get("id") for c in cases if not c.get("aborted")]
    coverage_html = ""
    if registered:
        uncovered = [c for c in registered if c not in covered]
        if uncovered:
            body = (
                f"This tier drives the shipped browser UI and does not reach "
                f"the whole roster. The cases it misses are validated on the "
                f"native-R tiers above and are <i>not</i> covered by any "
                f"wasm-vs-native claim. Not gated in this tier: "
                f"<code>{esc(', '.join(uncovered))}</code>.")
        else:
            body = (
                "Every registered case is driven through the shipped browser "
                "UI and compared against its own native-R display artifact "
                "&mdash; the ratio tables and Table 1 cell by cell, and the "
                "analyses that display a sentence rather than a table "
                "(Kaplan&ndash;Meier, group comparison) sentence by sentence.")
        coverage_html = (
            f"<p class=\"webr-totals\"><b>Coverage: {len(covered)} of "
            f"{len(registered)} cases.</b> {body}</p>")

    return (
        f"{header_html}{staleness_html}{coverage_html}{totals_html}"
        "<div class=\"scroll\"><table><thead><tr><th>Case</th>"
        "<th>Result</th><th>Strings compared</th><th>Detail</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>")


def build(findings_path: Path | str | None = None,
          out_path: Path | str | None = None,
          web_dir: Path | str | None = None) -> Path:
    findings_path = Path(findings_path) if findings_path else RESULTS / "findings.json"
    results_dir = findings_path.parent
    out_path = Path(out_path) if out_path else results_dir / "scorecard.html"
    # The shipped app sources the webR staleness check digests. A parameter only
    # so tests can point it at a fixture tree; in every real run it is the repo's
    # own web/.
    web_dir = Path(web_dir) if web_dir else WEB

    # An absent findings.json means compare.py never got as far as writing one.
    # Say that in one line instead of a traceback — and never fall back to
    # whatever scorecard.html happens to be sitting on disk.
    if not findings_path.exists():
        raise SystemExit(
            f"scorecard: no findings to publish ({findings_path} does not "
            "exist). compare.py writes it before it returns, so its absence "
            "means the comparator did not finish.")
    data = json.loads(findings_path.read_text())
    pending = _pending(data, results_dir)

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Figura statistical validation scorecard</title><style>{CSS}</style></head>
<body><main>
<h1>Statistical validation scorecard</h1>
<p class="sub">Every number Figura reports, re-derived from the same raw CSV by a
second implementation. Stated precisely: <b>one specification, transcribed from
the R sources by an agent with source access, was implemented a second time in
Python by agents that never read the R, against an acceptance suite whose
expected values were computed in R.</b> That catches implementation bugs,
library-default mismatches and arithmetic errors. It cannot catch a misreading
baked into the specification itself &mdash; both paths would reproduce it and
agree. See &ldquo;How the clean room actually worked, and its limits&rdquo; in
<code>stats-validation/README.md</code>, which discloses what the clean-room
bundle contained and two leak/retune episodes by commit hash.</p>
{_tiles(data, pending)}
<div class="scroll"><table>
<thead><tr><th>Case</th><th>Result</th><th>Coverage</th><th>Compared</th>
<th>Term</th><th>Quantity</th><th>Figura</th><th>Python</th></tr></thead>
<tbody>{_rows(data)}{_pending_rows(pending, results_dir)}</tbody></table></div>
<p class="sub"><b>Compared</b> names the two artifacts behind the Figura and
Python columns, in that order, because "Figura" is three different things
depending on the tier. <i>screen vs Python</i> checks the numbers the user was
actually shown against the independent implementation. <i>exported script vs
Python</i> checks the harvest from re-running the <code>.R</code> the app
exports &mdash; so a defect on that line indicts the <b>export path</b>, and
says nothing against the displayed numbers unless a <i>screen vs Python</i> row
fails too. <i>screen vs exported script</i> is Path A against itself: there the
Python column holds the exported script's own value, not Path B's.</p>
<p class="sub"><b>Coverage</b> ("targets met") means every quantity the case
declares in <code>exact_targets</code> was actually credited by a performed
comparison — a coverage failure marks a case TARGETS UNMET even if every
comparison that did run passed. <b>NOT COMPARED</b> marks a case that is
registered and ran, but whose two paths were never set against each other; it
carries no guarantee at all, and it is counted in the cases tile's denominator
so the tile can never read complete while such a case exists. <b>DEFERRED</b>
names declared coverage this run did not enforce because its comparison block
has not landed yet &mdash; not checked, so neither met nor failed.
<b>&ldquo;Targets met&rdquo; and MISSING QUANTITY measure two different
coverages, which is why a case can show both at once.</b> &ldquo;Targets
met&rdquo; &mdash; and the cases tile that counts it &mdash; is about the
quantities a case <i>declares</i> in its <code>exact_targets</code>: every
declared one was credited by a comparison that really ran. <b>Missing
quantity</b> is about a quantity that was <i>expected somewhere in the case and
never compared at all</i>, declared or not &mdash; the term the app displayed
that the exported script never produced, say. A case can therefore meet every
target it declared (green) while still publishing a MISSING QUANTITY row (red)
for something outside that declared set. Both statements are true; read them as
declared-target coverage and quantity coverage, not as one verdict contradicting
itself.
<b>Display artifact</b> means both paths
computed the same number and only the rendered string differs, within half a
display step. <b>Defect</b> means the values themselves disagree beyond a
relative tolerance of 1e-6. <b>Missing quantity</b> means something expected
was never compared at all &mdash; a coverage failure, not a value
disagreement. <b>Script divergence</b> means the exported .R does not
reproduce what the screen showed. <b>Count mismatch</b> means the two paths
analysed different rows. <b>Decision mismatch</b> means the two paths chose
different summary statistics for a Table 1 variable &mdash; mean &plusmn; SD
where the other chose median (IQR), say &mdash; which is a defect even when
every number in the row is individually correct. <b>Diagnostic mismatch</b>
means the two paths disagree about whether one of the app's ADVISORY sentences
&mdash; the C-statistic, VIF, EPV, Cook's-distance, separation or
proportional-hazards note &mdash; fires at all. Those sentences never change a
reported estimate, but they are printed for the user and pasted into a
manuscript, so a disagreement about one is published like any other.</p>
<p class="sub"><b>Published precision.</b> The Figura and Python columns above
are rounded to {PUBLISHED_SIGNIFICANT_DIGITS} significant digits <i>for
publication</i>. The comparison itself ran at full double precision &mdash; the
tolerances quoted above (relative 1e-6, absolute 1e-9) were applied to the
unrounded values, which stay in the pipeline's own intermediate artifacts. So
nothing here was judged at {PUBLISHED_SIGNIFICANT_DIGITS} digits; this page is
simply not in the business of publishing the last four digits of a double,
which differ between BLAS implementations and say nothing about the
statistics.</p>
<h2>WebR tier</h2>
<p class="sub">Everything above ran native R. This tier checks the claim only
this product has to make: that the same analyses, driven through the shipped
browser UI with R compiled to WebAssembly, display the same numbers. wasm has
no 80-bit extended precision and webR ships reference BLAS/LAPACK, so an
iterative fit is where a difference would appear. Cells are the strings the
user is shown, so a difference here is a difference a reader of the manuscript
would see.</p>
{_webr_section(results_dir, web_dir)}
</main></body></html>"""

    out_path.write_text(doc)
    return out_path


# ---------------------------------------------------------------------------
# THE PUBLIC PAGE — web/validation.html
#
# Same evidence as the scorecard above, a different reader: a clinician
# deciding whether to trust a number that is about to go into a manuscript,
# not a maintainer auditing a run. Four rules govern everything below.
#
#   1. IT LINKS styles.css; IT DOES NOT INLINE CSS. This page ships inside the
#      app, so it must age with the app's design tokens rather than freeze a
#      copy of them. The <style> block carries only what the stylesheet cannot
#      know about: a DOCUMENT layout instead of the fixed three-pane workbench,
#      and a dark-scheme remap of the SAME token names (the app itself ships
#      light-only, and styles.css is not this task's to edit).
#   2. IT ADDS NO NETWORK CALL. No CDN font, no external link; the Cloudflare analytics beacon is edge-injected and disclosed in the footer.
#      the no-egress invariant covers this page like every other byte of web/.
#      Every href here is relative and same-origin; `python -c` grep for
#      "http" over the built file is part of the verification.
#   3. IT IS THE SAME PURE FUNCTION build() is (see the module header): files
#      on disk in, HTML out — no clock, no environment, no `git rev-parse`. CI
#      byte-diffs the regenerated page exactly as it does the scorecard, so a
#      single live input would make the gate flap forever.
#   4. NOTHING MAY READ AS COMPLETE WHEN IT IS NOT. Every honesty guard the
#      scorecard grew — the registered-but-uncompared rows, the deferred
#      targets, the webR coverage ratio, the two staleness digests — is
#      rendered here too, in the reader's language rather than the
#      maintainer's.
# ---------------------------------------------------------------------------

WEB_PAGE = WEB / "validation.html"
CASES = Path(__file__).resolve().parent / "cases"

# figure -> the name the app itself uses in its nav rail (web/index.html), so a
# reader can map a row here onto the analysis they clicked.
ANALYSES = (
    ("summary", "Summary statistics (Table 1)"),
    ("km", "Kaplan-Meier"),
    ("groupcompare", "Group comparison"),
    ("cox", "Cox regression"),
    ("logistic", "Logistic regression"),
)
ANALYSIS_NAMES = dict(ANALYSES)

# What each display KIND compares beyond its declared exact targets. Restated
# from the compare_* branches in compare.py (compare_ratio_table,
# compare_km_summary, compare_gc_summary, compare_table1) — the display tier
# and the script tier are not in `exact_targets`, so they are invisible in
# findings.json and would otherwise go unstated on the page that is supposed to
# say what was checked.
KIND_TIERS = {
    "ratio_table": (
        "every cell of the rendered ratio table &mdash; unadjusted and "
        "adjusted, estimate, 95% CI and p-value &mdash; exactly as the app "
        "prints it",
        "the adjusted cells the exported <code>.R</code> produces when it is "
        "re-run in R, rendered through the app's own display rule",
    ),
    "km_summary": (
        "the median-survival and log-rank clauses of the sentence the app "
        "displays",
        "the medians and the log-rank p the exported <code>.R</code> produces "
        "when it is re-run in R",
    ),
    "gc_summary": (
        "the displayed test name, p-value and effect size, the per-group "
        "counts, and the full set of post-hoc pairs",
        "the p-value the exported <code>.R</code> produces when it is re-run "
        "in R",
    ),
    "table1": (
        "every displayed Table 1 cell, the missing-value counts and the row "
        "order",
        "the cells and the mean-vs-median choice the exported <code>.R</code> "
        "produces when it is re-run in R",
    ),
}

# What each kind does NOT compare. Stated per kind rather than once, because
# the gaps are different: KM's displayed sentence carries a hazard-ratio clause
# nothing parses, ratio_table's unadjusted column is a display claim only.
KIND_NOT_COMPARED = {
    "ratio_table": (
        "the unadjusted column at full precision (it is compared as "
        "displayed &mdash; only the joint model is harvested from the exported "
        "script); the prose wrapped around the numbers; the rendered forest "
        "plot, which draws the same adjusted estimates"
    ),
    "km_summary": (
        "the hazard-ratio clause of the displayed sentence; the rendered "
        "curve image (the curve itself is compared as coordinates)"
    ),
    "gc_summary": (
        "the prose wrapped around the numbers; the rendered box or bar plot"
    ),
    "table1": (
        "the prose wrapped around the table; the rendered distribution plots"
    ),
}

# case.json `exact_targets` -> plain language. Every key of
# compare.TARGET_QUANTITIES must appear here (test_scorecard.py pins that), so
# a target added to the contract can never render on a public page as a bare
# identifier a clinician cannot read.
TARGET_GLOSS = {
    "adjusted_or": "the adjusted odds ratio",
    "adjusted_hr": "the adjusted hazard ratio",
    "adjusted_ci": "its standard error and 95% confidence interval",
    "adjusted_p": "its p-value",
    "n": "the number of patients analysed",
    "n_event": "the number of events",
    "n_dropped": "the number of rows dropped",
    "c_statistic": "the C-statistic",
    "zph": "the global proportional-hazards test",
    "median_survival": "median survival in each group",
    "logrank_p": "the log-rank p-value",
    "curve": "every step of the survival curve",
    "test_p": "the test's p-value",
    "test_statistic": "the test statistic",
    "decisions": "the mean-vs-median choice for each variable",
    "vif_note": "the collinearity (VIF) advisory",
    "epv_note": "the events-per-variable advisory",
    "cooks_note": "the influential-observations advisory",
    "separation_note": "the separation caution",
    "ph_note": "the proportional-hazards advisory",
}

# The targets credited by the DISPLAY tier rather than the exact tier, so the
# page cannot claim full-precision agreement for a quantity that has no
# full-precision Path A value at all. Same split compare.TARGET_QUANTITIES
# documents at length: the exported script computes no VIF, no Cook's distance,
# no EPV and no separation check, and Table 1's `decisions` target is a choice
# rather than a number.
DISPLAY_TIER_TARGETS = frozenset({
    "decisions", "vif_note", "epv_note", "cooks_note", "separation_note",
    "ph_note",
})
# Of those, the ones that are advisory SENTENCES (compared for whether they
# fire). `decisions` is display-tier too but is not an advisory anything — it
# is Table 1's choice between mean and median, a published output in its own
# right — so it is glossed separately rather than filed under a heading that
# would understate it.
NOTE_TARGETS = frozenset(
    t for t in DISPLAY_TIER_TARGETS if t.endswith("_note"))

# compare.py's finding codes, in the reader's language. The codes themselves
# are printed unchanged — they are the published vocabulary, and a reader who
# opens findings.json must find the same words — with the gloss beside them.
CODE_GLOSS = {
    "COUNT_MISMATCH": "the two sides analysed a different number of rows",
    "MISSING_QUANTITY": "something expected was never compared at all &mdash; "
                        "a hole in the coverage, not a value disagreement",
    "DECISION_MISMATCH": "the two sides chose different summary statistics for "
                         "a Table 1 variable",
    "SCRIPT_DIVERGENCE": "the exported <code>.R</code> does not reproduce what "
                         "the screen showed",
    "DEFECT": f"the values themselves disagree, beyond a relative tolerance of "
              f"{REL_TOL:g}",
    "DIAGNOSTIC_MISMATCH": "the two sides disagree about whether one of the "
                           "app's advisory sentences fires at all",
    "DISPLAY_ARTIFACT": "both sides computed the same number; only the "
                        "rendered string differs, within half a display step",
}

# What the two value columns actually hold, per comparison. This is the single
# most misreadable thing on the page: on the export-path rows the "Figura"
# column is the app's own downloaded script, NOT the numbers the user saw.
SOURCE_GLOSS = {
    SRC_DISPLAY: "the numbers on screen, against the independent Python "
                 "implementation",
    SRC_EXACT: "the exported <code>.R</code> re-run in R, against the "
               "independent Python implementation",
    SRC_SCRIPT: "the numbers on screen, against Figura's own exported "
                "<code>.R</code>",
    SRC_SCREEN: "the displayed artifact alone &mdash; a one-sided finding, "
                "with no second value to compare against",
    SRC_HARVEST: "the exported script's output alone &mdash; a one-sided "
                 "finding",
    SRC_PATH_B: "the independent implementation's output alone &mdash; a "
                "one-sided finding",
    SRC_COVERAGE: "the case's declared coverage &mdash; a quantity it promised "
                  "to compare and did not",
}

# The one thing on this page that findings.json does not contain: WHY a case's
# exported script diverges. That is knowledge about a specific case, so it is
# keyed by case id and rendered only for that case. Any other export-path case
# gets the same structure WITHOUT a cause the page cannot know.
#
# EMPTY ON PURPOSE, and it must stay empty until a case publishes export-path
# findings again. It carried a `logistic-dirty` entry until the .script_data fix
# (issues/02) closed the divergence and that case went green. Both dicts are
# keyed off a case HAVING findings, so a stale entry would never render — which
# is exactly why it must be deleted rather than left sitting here: a dormant
# paragraph describing behaviour the app no longer has is a paragraph nobody
# will re-read before the day it renders again.
CASE_CAUSE: dict[str, str] = {}

# The disposition of a case's findings: open or fixed, tracked where, affecting
# whom. Case-specific knowledge again, keyed by id, so a case this file has
# never heard of cannot inherit another case's status. A case with findings and
# no entry here says so plainly instead (see _web_narrative). Empty for the same
# reason as CASE_CAUSE above.
CASE_STATUS: dict[str, str] = {}


def _case_figure(cases_dir: Path, case_id: str) -> str | None:
    """The analysis a case exercises, read from its own case.json.

    Never guessed from the case id: `logistic-dirty` happens to name its
    figure, but that is a convention, not a contract. An unreadable or absent
    case.json returns None and the case is grouped under a visibly-unknown
    analysis rather than silently filed under the wrong one.
    """
    path = Path(cases_dir) / case_id / "case.json"
    try:
        figure = json.loads(path.read_text()).get("figure")
    except (json.JSONDecodeError, OSError):
        return None
    return figure if isinstance(figure, str) else None


def _grouped_by_analysis(cases: list[dict], cases_dir: Path):
    """[(figure, [case, ...]), ...] in the app's own nav order.

    Analyses the app has but the harness does not cover contribute no row —
    they are named in the prose instead, since an empty row would read like a
    checked-and-passed one.
    """
    groups: dict[str | None, list[dict]] = {}
    for case in cases:
        groups.setdefault(_case_figure(cases_dir, case["id"]), []).append(case)
    ordered = [(fig, groups.pop(fig)) for fig, _ in ANALYSES if fig in groups]
    # Anything else (a new figure, or a case whose case.json could not be read)
    # still renders, sorted, under whatever name it gave — never dropped.
    ordered += [(fig, groups[fig]) for fig in sorted(groups, key=lambda f: f or "")]
    return ordered


def _analysis_name(figure: str | None) -> str:
    if figure is None:
        return "unknown (case.json unreadable)"
    return ANALYSIS_NAMES.get(figure, figure)


def _export_path_only(case: dict) -> bool:
    """Every finding on this case is Figura disagreeing with its OWN exported
    script, never with the independent implementation.

    This is the condition the plain-language narrative below depends on: it is
    what makes "the numbers on screen were right" a statement about the
    evidence rather than a hope. If a future run adds a `screen vs Python`
    finding, the narrative falls back to a generic block instead of repeating a
    reassurance the evidence no longer supports.
    """
    findings = case.get("findings") or []
    return bool(findings) and all(
        f.get("source") in (SRC_EXACT, SRC_SCRIPT) for f in findings)


def _export_path_findings(case: dict) -> list[dict]:
    """This case's findings that are about the exported script, whichever tier.

    Deliberately NOT `_export_path_only`, which asks whether ALL of a case's
    findings are export-path (the precondition for the "the numbers on screen
    were right" story, which one display finding falsifies). A case carrying
    one display finding and one export finding still hands the user a download
    that does not reproduce the app, and the download caveat must still fire
    for it — the reassurance is what has to be withheld, not the warning.
    """
    return [f for f in (case.get("findings") or [])
            if f.get("source") in (SRC_EXACT, SRC_SCRIPT)]


def _count_pairs(case: dict) -> dict:
    """{quantity: (exported script value, app value)} from COUNT_MISMATCH."""
    return {f["quantity"]: (f["figura"], f["python"])
            for f in case["findings"] if f["code"] == "COUNT_MISMATCH"}


# A ratio cell ("1.66 (1.24-2.23, p<0.001)") is one value and must never break
# across lines; a methods sentence is prose and must. Length is the honest
# discriminator here — the comparator publishes both kinds in the same column,
# and holding a 67-character sentence on one line is what pushed the second
# value column off the right-hand edge of the sheet.
LONG_VALUE = 34


def _value_cell(value) -> str:
    text = "" if value is None else str(value)
    cls = "num long" if len(text) > LONG_VALUE else "num"
    return f"<td class='{cls}'>{esc(text)}</td>"


def _row_label(f: dict) -> str:
    """What to call this row in the plain-language table.

    A whole-model finding (the C-statistic, a count) carries `term = "-"`,
    which is right for a machine-readable artifact and unreadable in a
    published table. Fall back to the quantity, minus the tier prefix the
    comparator puts in front of it.
    """
    term = f.get("term")
    if term and term != "-":
        return str(term)
    quantity = str(f.get("quantity") or "")
    return quantity.replace("exported script ", "") or "—"


WEB_CSS = """
/* validation.html — the app's own tokens, in a document layout.

   styles.css is LINKED, never copied and never edited from here, so this page
   cannot drift from the shipped design system. What follows is only what a
   stylesheet built for a fixed three-pane workbench cannot provide: a
   scrolling document, and a dark-scheme remap of the same variable names (the
   app ships light-only). Every colour below is a token, never a literal. */

/* The workbench pins html/body to the viewport and lays body out as a flex
   column. A document scrolls instead. */
html, body { height: auto; }
body { display: block; font-size: 14px; line-height: 1.6; }

/* Dark scheme: the same token names, re-pointed. Because every rule here and
   in styles.css reads the variables rather than literals, this is the whole of
   it — no second colour vocabulary, no duplicated rules. */
@media (prefers-color-scheme: dark) {
  :root {
    --chrome: #14130f;
    --panel: #1c1b16;
    --panel-raised: #232219;
    --rail: #191813;
    --output-canvas: #14130f;
    --segment-track: #232219;
    --sheet: #1f1e18;
    --ink: #ece7dc;
    --ink-2: #ddd8cc;
    --ink-muted: #a49e90;
    --ink-faint: #7c766a;
    --line: #2e2c24;
    --line-soft: #29271f;
    --border-card: #3a372d;
    --sheet-border: #35322a;
    --accent: #5cb8ac;
    --accent-dark: #7fd0c4;
    --accent-wash: #172724;
    --accent-tint-border: #2c4a45;
    --ok: #74c08d;
    --error: #e8877a;
    --warn-bg: #2a2317;
    --warn-border: #4b3f25;
    --warn-ink: #e0b877;
    --shadow-pane: 0 1px 2px rgba(0, 0, 0, .45), 0 2px 10px rgba(0, 0, 0, .35);
    --shadow-sheet: 0 1px 0 #2a2820, 0 18px 44px -22px rgba(0, 0, 0, .8);
  }
}

/* ---- Document frame ----------------------------------------------------- */

/* Wider than the reading measure below on purpose: the prose is capped at
   40rem wherever it appears, and the extra width goes to the evidence tables,
   which have seven columns and must not push the second value column off the
   edge of a laptop screen. */
.doc { max-width: 58rem; margin: 0 auto; padding: 12px 10px 3.5rem; }

/* The pane treatment from the workbench: a card floating on the warm desk. */
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-pane);
  padding: 2rem 2.25rem 2.5rem;
}

/* Measure. Tables and figures may use the full card; prose may not. */
.doc p, .doc li, .lede, .toc { max-width: 40rem; text-wrap: pretty; }

.eyebrow {
  margin: 0 0 .5rem;
  font: .6875rem/1 var(--mono);
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--ink-muted);
}

.doc h1 {
  margin: 0 0 .625rem;
  font: 600 1.75rem/1.2 var(--serif);
  letter-spacing: -.01em;
}

.lede { font: 1rem/1.6 var(--serif); color: var(--ink-2); margin: 0 0 1.25rem; }

.doc h2 {
  margin: 2.5rem 0 .75rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--line);
  font: 600 1.1875rem/1.25 var(--serif);
}

.doc h3 { margin: 1.75rem 0 .375rem; font: 600 1rem/1.35 var(--serif); }
.doc h4 { margin: 1.25rem 0 .25rem; font-size: .8125rem; font-weight: 650; }
.doc ul { padding-left: 1.125rem; }
.doc li { margin: .25rem 0; }

.doc code {
  font: .8125em var(--mono);
  background: var(--panel-raised);
  border: 1px solid var(--line-soft);
  border-radius: 3px;
  padding: 0 .25rem;
  overflow-wrap: anywhere;
}

.doc a { color: var(--accent); text-underline-offset: 2px; }
.doc a:hover { color: var(--accent-dark); }

/* ---- Masthead ----------------------------------------------------------- */

/* .toolbar/.brand/.mark come from styles.css unchanged — the page wears the
   app's own chrome. Only the wordmark needs restating, because in the app it
   is an <h1> and here the <h1> belongs to the document. */
.wordmark {
  font: 600 1.0625rem/1.4 var(--serif);
  letter-spacing: -.01em;
  color: var(--ink);
}
.brand-link { display: flex; align-items: center; gap: .625rem; text-decoration: none; }
.back-link { font: .75rem var(--mono); color: var(--ink-muted); text-decoration: none; }
.back-link:hover { color: var(--accent); text-decoration: underline; }

/* ---- Tiles -------------------------------------------------------------- */

.tiles { display: flex; flex-wrap: wrap; gap: .625rem; margin: 1.5rem 0 1rem; }
.tile {
  flex: 1 1 9rem;
  background: var(--panel-raised);
  border: 1px solid var(--border-card);
  border-radius: var(--radius-card);
  padding: .8125rem .9375rem;
}
.tile b {
  display: block;
  font: 600 1.5rem/1.1 var(--mono);
  font-variant-numeric: tabular-nums;
}
.tile span {
  display: block;
  margin-top: .25rem;
  font: .625rem var(--mono);
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--ink-muted);
}

.verdict { font: .9375rem/1.6 var(--serif); color: var(--ink-2); }

/* ---- Boxes -------------------------------------------------------------- */

.claim {
  margin: 1.5rem 0;
  padding: 1rem 1.25rem;
  background: var(--accent-wash);
  border: 1px solid var(--accent-tint-border);
  border-radius: var(--radius-card);
}
.claim p { margin: 0 0 .625rem; }
.claim p:last-child { margin-bottom: 0; }

/* The open defect gets the app's own warn treatment — the same one the
   synthetic-data banner wears, because it carries the same kind of weight:
   read this before you rely on what is around it. */
.warn-box {
  margin: 1.25rem 0;
  padding: .75rem 1rem;
  color: var(--warn-ink);
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  border-radius: var(--radius-ctl);
}
.warn-box p { margin: 0 0 .5rem; }
.warn-box p:last-child { margin-bottom: 0; }

.aside {
  margin: 1rem 0;
  padding-left: .875rem;
  border-left: 2px solid var(--border-card);
  color: var(--ink-muted);
  font-size: .8125rem;
}

.toc { margin: 1.25rem 0 0; padding: 0; list-style: none; }
.toc li { margin: .1875rem 0; font: .8125rem var(--sans); }

/* ---- Tables: the journal galley, on cells rather than on the table ------- */

/* The wrapper is the sheet, and it is what scrolls on a narrow screen — never
   the page body. Same contract R's own .summary-output > .table-scroll has. */
.table-sheet {
  overflow-x: auto;
  background: var(--sheet);
  border: 1px solid var(--sheet-border);
  border-radius: var(--radius-sheet);
  box-shadow: var(--shadow-sheet);
  padding: 1.5rem 1.75rem 1.25rem;
  margin: 1rem 0 1.5rem;
}

.val-table {
  border-collapse: collapse;
  width: 100%;
  font: .8125rem var(--sans);
  color: var(--ink);
}
.val-table th, .val-table td {
  padding: .375rem .875rem;
  border: none;
  text-align: left;
  vertical-align: top;
}
.val-table th:first-child, .val-table td:first-child { padding-left: 0; }
.val-table th:last-child, .val-table td:last-child { padding-right: 0; }
.val-table thead th {
  font: 600 .6875rem var(--mono);
  letter-spacing: .02em;
  border-top: 1.5px solid var(--ink);
  border-bottom: 1px solid var(--ink);
  padding-top: .5rem;
  padding-bottom: .5rem;
  white-space: nowrap;
}
/* The row-identifying cell of every table here is a <th scope="row"> — a screen
   reader announces it with each cell of its row, which is the whole point of a
   table of case ids. Visually it must stay the quiet cell it always was, so the
   UA's bold is dropped; the analysis column bolds its own name with <b>. */
.val-table tbody th { font-weight: 400; }
.val-table tbody tr:last-child td,
.val-table tbody tr:last-child th { border-bottom: 1.5px solid var(--ink); }
.val-table tbody tr:hover td,
.val-table tbody tr:hover th { background: var(--line-soft); }
.val-table ul { margin: .25rem 0 .5rem; padding-left: 1rem; }
.val-table li { margin: .125rem 0; max-width: 34rem; }
.val-table .case-id, .val-table .num {
  font-family: var(--mono);
  font-size: .71875rem;
  font-variant-numeric: tabular-nums;
}
.val-table .case-id { white-space: nowrap; }
/* An estimate and its interval are one value: never break "1.66 (1.24-2.23)"
   across lines — the sheet scrolls instead. A methods SENTENCE is not one
   value, and holding it on one line is what pushed the second value column off
   the page, so anything long enough to be prose wraps like prose. */
.val-table .num { white-space: nowrap; }
.val-table .num.long { white-space: normal; overflow-wrap: anywhere; }
.val-table .tier { font: .6875rem var(--mono); color: var(--ink-muted); }
/* One case id per line: they are long, hyphenated and mono, and inline they
   wrap mid-token into something that reads like two ids. */
.case-chip {
  display: block;
  font: .6875rem var(--mono);
  white-space: nowrap;
  color: var(--ink-muted);
}

/* Verdict colours, from the app's signal tokens. A difference is never quiet
   and a pass is never loud. */
.v-pass { color: var(--ok); }
.v-warn { color: var(--warn-ink); font-weight: 600; }
.v-fail { color: var(--error); font-weight: 600; }
.v-code { font: 600 .6875rem var(--mono); letter-spacing: .02em; white-space: nowrap; }

.doc-foot {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
  font-size: .75rem;
  color: var(--ink-muted);
}
.doc-foot p { margin: .25rem 0; max-width: 44rem; }

/* ---- Responsive --------------------------------------------------------- */

@media (max-width: 720px) {
  .doc { padding: 8px 8px 2.5rem; }
  .card { padding: 1.25rem 1.125rem 1.75rem; }
  .table-sheet { padding: 1rem .875rem .75rem; }
  .doc h1 { font-size: 1.5rem; }
  .tile { flex: 1 1 7rem; }
  .tile b { font-size: 1.25rem; }
  /* A five- or six-column evidence table cannot be squeezed into a phone: at
     100% width the percentage columns collapse to two or three words each and
     a paragraph-length cell becomes a vertical ribbon. Give the table a floor
     and let THE SHEET scroll — the same contract R's own rendered tables have
     in the app (.summary-output > .table-scroll), and the reason the page body
     itself never scrolls sideways. */
  .val-table { min-width: 40rem; }
}

/* Touch: 16px is the documented floor for anything interactive (iOS Safari
   zooms a smaller control on focus and never zooms back), and the body text
   goes up with it — this page is read, not operated. */
@media (pointer: coarse) {
  body { font-size: 16px; }
  .doc a, .doc summary { min-height: 24px; }
  .back-link { font-size: 16px; }
}
"""


# Small counts read as prose on this page, not as figures; anything larger
# falls back to digits rather than growing a spelling table nobody maintains.
NUMBER_WORDS = {
    0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
}


def _count_word(n: int) -> str:
    return NUMBER_WORDS.get(n, str(n))


def _web_tiles(data: dict, pending: list[str]) -> str:
    """The headline counts. Same numbers as the scorecard's tiles, same
    refusal to let any of them read as complete: the denominator is every
    REGISTERED case, and a case with deferred targets does not count as
    fully covered.

    The coverage tile borrows the case table's own wording ("declared coverage:
    complete") deliberately. "8 of 8 cases fully covered", sitting beside "1 of
    8 cases with differences", reads as "everything was checked" — which is the
    one thing this page must never say, since coverage is what each case
    DECLARED it would compare, not the whole of what the app computes."""
    cases = data["cases"]
    with_findings = [c for c in cases if c["findings"]]
    total = len(cases) + len(pending)
    met = sum(1 for c in cases
              if c["targets_met"] and not c.get("deferred_targets"))
    deferred_cases = sum(1 for c in cases if c.get("deferred_targets"))
    extra = ""
    if deferred_cases:
        extra += (f'<div class="tile"><b class="v-warn">{deferred_cases}</b>'
                  f'<span>cases with unchecked declared coverage</span></div>')
    if pending:
        extra += (f'<div class="tile"><b class="v-warn">{len(pending)}</b>'
                  f'<span>cases run but never compared</span></div>')
    findings_class = "v-fail" if data["total_findings"] else "v-pass"
    cases_class = "v-fail" if with_findings else "v-pass"
    return f"""<div class="tiles">
  <div class="tile"><b>{esc(data['total_compared'])}</b>
    <span>values compared</span></div>
  <div class="tile"><b class="{findings_class}">{esc(data['total_findings'])}</b>
    <span>differences found</span></div>
  <div class="tile"><b class="{cases_class}">{len(with_findings)} of {total}</b>
    <span>cases with differences</span></div>
  <div class="tile"><b>{met} of {total}</b>
    <span>cases with declared coverage complete</span></div>{extra}
</div>"""


def _web_verdict(data: dict, pending: list[str]) -> str:
    """One sentence a reader can stop at, derived from the findings alone."""
    cases = data["cases"]
    with_findings = [c for c in cases if c["findings"]]
    clean = len(cases) - len(with_findings)
    total = len(cases) + len(pending)
    if not with_findings:
        return ('<p class="verdict">Every compared value matched. That is the '
                'whole of what these cases checked &mdash; read '
                '<a href="#checked">what was checked</a> before reading it as '
                'more.</p>')
    export_only = all(_export_path_only(c) for c in with_findings)
    where = ("one case" if len(with_findings) == 1
             else f"{len(with_findings)} cases")
    if export_only:
        return (
            f'<p class="verdict">{clean} of the {total} cases match exactly. '
            f'All {data["total_findings"]} differences are on {where}, and '
            f'every one of them is Figura disagreeing with the '
            f'<code>.R</code> script it offers you to download &mdash; not '
            f'with the independent implementation. <b>The numbers on screen '
            f'were right;</b> the downloaded script was not. '
            f'<a href="#differences">What that means for you</a>.</p>')
    return (
        f'<p class="verdict">{clean} of the {total} cases match exactly. '
        f'{data["total_findings"]} differences remain, on {where}. '
        f'<a href="#differences">Read them</a> before relying on the '
        f'analyses they name.</p>')


def _web_coverage_table(data: dict, cases_dir: Path) -> str:
    """What is compared, per analysis — and what is not.

    Built from the cases' own declared `targets` (the quantities a comparison
    really credited) plus the per-kind display and script tiers, so a case that
    stopped comparing something cannot leave this table claiming it still does.
    """
    rows = []
    for figure, cases in _grouped_by_analysis(data["cases"], cases_dir):
        kinds = sorted({c["kind"] for c in cases})
        exact, notes, decisions = [], [], []
        for key in dict.fromkeys(k for c in cases for k in c["targets"]):
            gloss = TARGET_GLOSS.get(key, f"<code>{esc(key)}</code>")
            if key in NOTE_TARGETS:
                notes.append(gloss)
            elif key in DISPLAY_TIER_TARGETS:
                decisions.append(gloss)
            else:
                exact.append(gloss)
        items = []
        for kind in kinds:
            display_tier, script_tier = KIND_TIERS.get(kind, (None, None))
            if display_tier:
                items.append(
                    f"<li><b>As displayed</b> &mdash; {display_tier}, compared "
                    f"character for character.</li>")
            if script_tier:
                items.append(
                    f"<li><b>The downloaded script</b> &mdash; {script_tier}, "
                    f"compared against the screen.</li>")
        if exact:
            items.insert(0, (
                f"<li><b>At full precision</b> (agreement to a relative "
                f"{REL_TOL:g}) &mdash; {', '.join(exact)}.</li>"))
        if decisions:
            items.append(
                f"<li><b>The choice of statistic</b> &mdash; not just the "
                f"number but which one: {', '.join(decisions)}.</li>")
        if notes:
            items.append(
                f"<li><b>Advisory sentences</b> &mdash; whether each one fires "
                f"at all: {', '.join(notes)}.</li>")
        not_compared = " ".join(
            KIND_NOT_COMPARED[k] for k in kinds if k in KIND_NOT_COMPARED)
        case_list = "".join(
            f"<span class='case-chip'>{esc(c['id'])}</span>" for c in cases)
        rows.append(
            f"<tr><th scope=\"row\"><b>{esc(_analysis_name(figure))}</b><br>"
            f"<span class='tier'>{len(cases)} case"
            f"{'s' if len(cases) != 1 else ''}</span>{case_list}</th>"
            f"<td><ul>{''.join(items)}</ul></td>"
            f"<td>{not_compared or '&mdash;'}</td></tr>")
    return (
        "<div class=\"table-sheet\"><table class=\"val-table\">"
        "<colgroup><col style=\"width:20%\"><col style=\"width:48%\">"
        "<col style=\"width:32%\"></colgroup><thead><tr>"
        "<th scope=\"col\">Analysis</th><th scope=\"col\">What is compared</th>"
        "<th scope=\"col\">What is not</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def _web_case_table(data: dict, pending: list[str], cases_dir: Path) -> str:
    """One row per case: what it exercised, how much was compared, how it came
    out. Registered-but-uncompared cases get their own visibly-incomplete row,
    exactly as on the scorecard — a case that carries no guarantee must never
    be invisible on the page that publishes the guarantees."""
    rows = []
    for case in data["cases"]:
        findings = case["findings"]
        if findings:
            result = (f"<span class='v-fail'>{len(findings)} difference"
                      f"{'s' if len(findings) != 1 else ''}</span> "
                      f"&mdash; <a href='#differences'>read them</a>")
        else:
            result = "<span class='v-pass'>no differences</span>"
        deferred = case.get("deferred_targets") or []
        if deferred:
            coverage = (f"<span class='v-warn'>{len(deferred)} not checked</span>"
                        f"<br><span class='tier'>{esc(', '.join(deferred))}"
                        f"</span>")
        elif case["targets_met"]:
            coverage = "<span class='v-pass'>complete</span>"
        else:
            coverage = "<span class='v-fail'>INCOMPLETE</span>"
        rows.append(
            f"<tr><th scope=\"row\" class='case-id'>{esc(case['id'])}</th>"
            f"<td>{esc(_analysis_name(_case_figure(cases_dir, case['id'])))}</td>"
            f"<td class='num'>{esc(case['compared'])}</td>"
            f"<td>{coverage}</td><td>{result}</td></tr>")
    for case_id in pending:
        rows.append(
            f"<tr><th scope=\"row\" class='case-id'>{esc(case_id)}</th>"
            f"<td>{esc(_analysis_name(_case_figure(cases_dir, case_id)))}</td>"
            f"<td class='num'>0</td>"
            f"<td><span class='v-warn'>NONE</span></td>"
            f"<td><span class='v-warn'>never compared</span> &mdash; this case "
            f"ran but its two implementations were never set against each "
            f"other, so it carries no guarantee at all</td></tr>")
    return (
        "<div class=\"table-sheet\"><table class=\"val-table\"><thead><tr>"
        "<th scope=\"col\">Case</th><th scope=\"col\">Analysis</th>"
        "<th scope=\"col\">Values compared</th>"
        "<th scope=\"col\">Declared coverage</th><th scope=\"col\">Result</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def _web_narrative(case: dict) -> str:
    """The findings of one case, in clinical language, from the findings alone.

    Every number here is read out of findings.json. The only sentence that is
    not derivable — WHY the exported script diverges — comes from CASE_CAUSE
    and renders only for a case that has an entry there. A case whose findings
    are not export-path-only gets the generic block instead, because the
    reassurance in the export-path story ("the numbers on screen were right")
    would then be false.
    """
    findings = case["findings"]
    case_id = esc(case["id"])
    if not _export_path_only(case):
        sources = sorted({f.get("source") or "unattributed" for f in findings})
        return (
            f"<h3>{case_id} &mdash; {len(findings)} differences</h3>"
            f"<p>These differences are not all on the export path: they were "
            f"raised by {esc(', '.join(sources))}. Read the table below in "
            f"full &mdash; the export-path explanation elsewhere on this page "
            f"does not cover them, and nothing here should be read as a "
            f"statement that the displayed numbers agree.</p>")

    counts = _count_pairs(case)
    script_cells = [f for f in findings if f["code"] == "SCRIPT_DIVERGENCE"]
    missing = [f for f in findings if f["code"] == "MISSING_QUANTITY"]
    parts = [f"<h3>{case_id} &mdash; {len(findings)} differences, all on the "
             f"downloaded script</h3>"]
    parts.append(CASE_CAUSE.get(case["id"], ""))

    count_rows = []
    labels = {"n": "patients analysed", "n_event": "patients with the outcome",
              "n_dropped": "rows dropped"}
    for quantity, (script, app) in counts.items():
        count_rows.append(
            f"<tr><th scope=\"row\">{esc(labels.get(quantity, quantity))}</th>"
            f"{_value_cell(app)}{_value_cell(script)}</tr>")
    for f in script_cells:
        count_rows.append(
            f"<tr><th scope=\"row\">{esc(_row_label(f))}</th>"
            f"{_value_cell(f['figura'])}{_value_cell(f['python'])}</tr>")
    for f in missing:
        count_rows.append(
            f"<tr><th scope=\"row\">{esc(_row_label(f))}</th>"
            f"<td class='num'>shown in the table</td>"
            f"<td class='num v-fail'>absent entirely</td></tr>")
    if count_rows:
        parts.append(
            "<div class=\"table-sheet\"><table class=\"val-table\">"
            "<colgroup><col style=\"width:24%\"><col style=\"width:38%\">"
            "<col style=\"width:38%\"></colgroup><thead><tr>"
            "<th scope=\"col\">Quantity</th><th scope=\"col\">Figura</th>"
            "<th scope=\"col\">The downloaded <code>.R</code></th></tr></thead>"
            f"<tbody>{''.join(count_rows)}</tbody></table></div>"
            "<p class=\"aside\">For the estimates, the Figura column is the "
            "string the app displayed. For the counts, it is what the "
            "independent implementation computed from the same file &mdash; "
            "the app's own displayed estimates match it cell for cell, which "
            "is what this case's passing display comparison means.</p>")

    parts.append(
        "<p><b>The displayed numbers were right.</b> On this case the app's "
        "screen and the independent Python implementation agree completely "
        "&mdash; that comparison passed, and it is the comparison that speaks "
        "to what you read off the screen. Every difference above is between "
        "Figura and its own exported script.</p>")
    parts.append(CASE_STATUS.get(
        case["id"],
        "<p class=\"aside\">This case has no recorded disposition in "
        "<code>build_scorecard.py</code>'s <code>CASE_STATUS</code>, so this "
        "page cannot say whether the differences above are being worked on. "
        "Read the case's own files under <code>stats-validation/</code>.</p>"))
    return "".join(parts)


def _web_findings_table(data: dict) -> str:
    """Every finding, unabridged, with the comparison named on each row."""
    # The case column earns its width only when there is more than one case to
    # tell apart. With a single failing case it repeats the same id down the
    # page and squeezes the two VALUE columns — the ones the reader came for —
    # off the right-hand edge of the sheet.
    failing = [c for c in data["cases"] if c["findings"]]
    show_case = len(failing) > 1
    rows = []
    for case in failing:
        for f in case["findings"]:
            case_cell = (f"<th scope=\"row\" class='case-id'>"
                         f"{esc(case['id'])}</th>" if show_case else "")
            rows.append(
                f"<tr>{case_cell}"
                f"<td class='v-code v-fail'>{esc(f['code'])}</td>"
                f"<td class='tier'>{esc(f.get('source') or '—')}</td>"
                f"<td>{esc(f['term'])}</td><td>{esc(f['quantity'])}</td>"
                f"{_value_cell(f['figura'])}{_value_cell(f['python'])}</tr>")
    if not rows:
        return ""
    case_header = "<th scope=\"col\">Case</th>" if show_case else ""
    case_note = ("" if show_case else
                 f"<p>Every row below is case "
                 f"<code>{esc(failing[0]['id'])}</code>.</p>")
    codes = dict.fromkeys(f["code"] for c in data["cases"] for f in c["findings"])
    sources = dict.fromkeys(
        f.get("source") for c in data["cases"] for f in c["findings"])
    code_legend = "".join(
        f"<li><code>{esc(code)}</code> &mdash; "
        f"{CODE_GLOSS.get(code, 'see stats-validation/compare/compare.py')}</li>"
        for code in codes)
    source_legend = "".join(
        f"<li><b>{esc(src)}</b> &mdash; "
        f"{SOURCE_GLOSS.get(src, 'see stats-validation/compare/compare.py')}"
        f"</li>" for src in sources if src)
    return (
        "<h3>Every difference, unabridged</h3>"
        "<p>The two value columns hold different artifacts on different rows, "
        "so each row names its own comparison. Read that column first:</p>"
        f"<ul>{source_legend}</ul>"
        f"<p>And the finding codes, which are the same words "
        f"<code>findings.json</code> uses:</p><ul>{code_legend}</ul>"
        f"{case_note}"
        "<div class=\"table-sheet\"><table class=\"val-table\"><thead><tr>"
        f"{case_header}<th scope=\"col\">Code</th>"
        "<th scope=\"col\">Comparison</th><th scope=\"col\">Term</th>"
        "<th scope=\"col\">Quantity</th><th scope=\"col\">Figura</th>"
        "<th scope=\"col\">Python</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        f"<p class=\"aside\">Values are rounded to "
        f"{PUBLISHED_SIGNIFICANT_DIGITS} significant digits for publication. "
        f"The comparison itself ran at full double precision, at a relative "
        f"tolerance of {REL_TOL:g} &mdash; nothing here was judged at "
        f"{PUBLISHED_SIGNIFICANT_DIGITS} digits. This page simply is not in "
        f"the business of publishing the last digits of a double, which differ "
        f"between linear-algebra libraries and say nothing about the "
        f"statistics.</p>")


def _web_differences_section(data: dict) -> str:
    with_findings = [c for c in data["cases"] if c["findings"]]
    if not with_findings:
        return (
            "<p>No case currently publishes a difference. That is not the same "
            "as \"nothing can be wrong\": read "
            "<a href=\"#checked\">what was checked</a> for the boundary of the "
            "claim, and the limits stated at the top of this page for what a "
            "specification-based re-implementation cannot catch in "
            "principle.</p>"
            "<p class=\"aside\">A validation page that only ever shows green "
            "is not evidence. When this harness finds something, it is "
            "published here, in this section, before it is fixed.</p>")
    parts = [
        "<p>Differences are published here <b>before</b> they are fixed, and "
        "they are described in the terms that matter clinically: which "
        "patients were analysed, and which number changed.</p>"
    ]
    parts += [_web_narrative(c) for c in with_findings]
    parts.append(_web_findings_table(data))
    return "".join(parts)


def _undriftable_clause(cases: list, total, numeric) -> str:
    """What the OTHER strings are — derived from the evidence, never asserted.

    THE BUG THIS EXISTS FOR. The sentence used to read "The rest are column
    headers, row labels and deliberately blank cells, which cannot drift."
    That was true of the two-ratio-table roster it was written for. On the
    eight-case roster it was wrong by 8 units: of the 55 non-numeric strings,
    47 are headers/labels/blank cells and the other 8 are DISPLAYED SENTENCES
    that happen to carry no number — a shape the sentence did not know
    existed. So the split is now summed from each case's own `cell_kinds`
    rather than written down, and it cannot go stale when the roster's mix of
    shapes changes again.

    IT REFUSES RATHER THAN GUESSES. The clause is only rendered when the
    summed kinds actually reconcile with the two published totals
    (value + methods_with_number == cells_with_numbers, and all five kinds
    == cells_compared). A webr-tier.json written before `cell_kinds` existed,
    or one whose per-case breakdowns do not add up to its own totals, gets a
    sentence that claims no split at all instead of a fabricated arithmetic.

    Aborted cases contribute nothing here — they compared nothing, and the
    totals they are being reconciled against are sums over completed cases.
    """
    generic = ("The rest are labels and fixed wording, which cannot drift.")
    keys = ("header", "term", "value", "empty", "methods",
            "methods_with_number")
    agg = {k: 0 for k in keys}
    seen = False
    for c in cases:
        if c.get("aborted"):
            continue
        kinds = c.get("cell_kinds")
        if not isinstance(kinds, dict):
            continue
        seen = True
        for k in keys:
            value = kinds.get(k)
            if not isinstance(value, int) or isinstance(value, bool):
                return generic
            agg[k] += value
    if not seen or not isinstance(total, int) or not isinstance(numeric, int):
        return generic
    static = agg["header"] + agg["term"] + agg["empty"]
    prose = agg["methods"] - agg["methods_with_number"]
    if prose < 0:
        return generic
    if agg["value"] + agg["methods_with_number"] != numeric:
        return generic
    if static + agg["methods"] + agg["value"] != total:
        return generic
    rest = total - numeric
    if rest != static + prose:
        return generic
    if rest == 0:
        return "Every compared string carries a number."
    clauses = []
    if static:
        clauses.append(
            f"<b>{static}</b> are column headers, row labels and deliberately "
            f"blank cells")
    if prose:
        clauses.append(
            f"<b>{prose}</b> {'is a' if prose == 1 else 'are'} displayed "
            f"sentence{'' if prose == 1 else 's'} that carr"
            f"{'ies' if prose == 1 else 'y'} no number")
    return (f"The other <b>{rest}</b> string{'' if rest == 1 else 's'} cannot "
            f"drift: " + ", and ".join(clauses) + ".")


def _web_webr_section(results_dir: Path, web_dir: Path) -> str:
    """The wasm-vs-native-R tier, for the reader who actually runs webR.

    Reuses the scorecard's own staleness digests rather than restating them:
    if the native numbers or the shipped app have moved since the gate was
    hand-run, this page says so instead of quietly presenting old evidence as
    current.

    An ABORTED case is deliberately NOT counted as coverage — see the same
    argument spelled out in `_webr_section`'s docstring. Both surfaces must
    agree, because both are rendered from the same file by the same `make`.
    """
    path = Path(results_dir) / "webr-tier.json"
    if not path.exists():
        return ("<div class=\"warn-box\"><p>This gate has not been run for the "
                "current release, so there is <b>no</b> published "
                "wasm-vs-native-R evidence right now. It is deleted before "
                "every run, so an empty section means \"not run\", never "
                "\"last release's numbers still apply\".</p></div>")
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return ("<div class=\"warn-box\"><p>The webR tier's evidence file is "
                "present but could not be read as JSON, so nothing is claimed "
                "here.</p></div>")

    cases = raw.get("cases") or []
    registered = registered_cases(Path(results_dir))
    # Aborted cases compared nothing, so they are not coverage. See
    # _webr_section's docstring for why this is reachable rather than
    # theoretical.
    covered = [c.get("id") for c in cases if not c.get("aborted")]
    rows = []
    for c in cases:
        if c.get("aborted"):
            rows.append(
                f"<tr><th scope=\"row\" class='case-id'>{esc(c.get('id'))}</th>"
                f"<td class='v-fail'>ABORTED</td><td class='num'>&mdash;</td>"
                f"<td>The run did not complete a comparison for this case: "
                f"{esc(c.get('reason'))}</td>"
                f"</tr>")
            continue
        identical = bool(c.get("identical"))
        differing = c.get("differing_cells") or []
        if identical:
            verdict = "<span class='v-pass'>identical</span>"
            detail = ("every displayed string matched native R exactly")
        else:
            verdict = "<span class='v-fail'>DIFFERS</span>"
            detail = "".join(
                f"<li><b>{esc(d.get('term'))}</b> / {esc(d.get('column'))}: "
                f"native R <code>{esc(d.get('native'))}</code>, webR "
                f"<code>{esc(d.get('webr'))}</code></li>" for d in differing)
            n = len(differing)
            detail = (f"{n} of {esc(c.get('cells_compared'))} "
                      f"string{'' if n == 1 else 's'} "
                      f"differ{'s' if n == 1 else ''}<ul>{detail}</ul>")
        rows.append(
            f"<tr><th scope=\"row\" class='case-id'>{esc(c.get('id'))}</th>"
            f"<td>{verdict}</td>"
            f"<td class='num'>{esc(c.get('cells_compared'))}</td>"
            f"<td>{detail}</td></tr>")
    if not rows:
        rows.append("<tr><td colspan='4'>The evidence file lists no cases.</td>"
                    "</tr>")

    total = raw.get("cells_compared")
    numeric = raw.get("cells_with_numbers")
    totals = ""
    if total is not None and numeric is not None:
        note = raw.get("cells_note")
        totals = (
            f"<p>Every one of the <b>{esc(total)}</b> strings the app displays "
            f"across these cases was compared &mdash; <b>{esc(numeric)}</b> of "
            f"them carrying a number that could actually move between native R "
            f"and WebAssembly. {_undriftable_clause(cases, total, numeric)}</p>"
            + (f"<p class=\"aside\">{esc(note)}</p>" if note else ""))

    coverage = ""
    if registered:
        uncovered = [c for c in registered if c not in covered]
        if uncovered:
            body = (
                f"This gate drives the real browser interface and does not "
                f"reach the whole roster. The cases it misses are validated on "
                f"native R above and are <i>not</i> covered by any "
                f"wasm-vs-native claim. Not gated here: "
                f"<code>{esc(', '.join(uncovered))}</code>.")
        else:
            body = (
                "Every case on this page was also run through the real browser "
                "interface and checked against native R &mdash; the tables cell "
                "by cell, and the analyses that report a sentence rather than a "
                "table (Kaplan&ndash;Meier, group comparison) sentence by "
                "sentence.")
        coverage = (f"<p><b>Coverage: {len(covered)} of {len(registered)} "
                    f"cases.</b> {body}</p>")

    stale = ""
    stale_native = _stale_native_digest(
        raw, Path(results_dir),
        [c.get("id") for c in cases if not c.get("aborted")])
    if stale_native:
        stale += ("<p>The native-R numbers this evidence was compared against "
                  "have changed since the gate ran, so it describes an older "
                  "set of results. It needs re-running.</p>")
    if _stale_web_digest(raw, Path(web_dir)):
        stale += ("<p>The shipped app has changed since this evidence was "
                  "measured, so it describes a browser run of an earlier "
                  "version of the app. It needs re-running.</p>")
    if stale:
        stale = f"<div class=\"warn-box\">{stale}</div>"

    commit = raw.get("commit")
    provenance = (
        f"<p class=\"aside\">Runtime <code>{esc(raw.get('runtime'))}</code>, "
        f"run {esc(raw.get('date'))}"
        + (f", against commit <code>{esc(str(commit)[:12])}</code>"
           if commit else "")
        + f". {esc(raw.get('runtime_source') or '')}</p>")

    return (
        f"{stale}{provenance}{coverage}{totals}"
        "<div class=\"table-sheet\"><table class=\"val-table\"><thead><tr>"
        "<th scope=\"col\">Case</th><th scope=\"col\">Result</th>"
        "<th scope=\"col\">Strings compared</th><th scope=\"col\">Detail</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def _web_download_caveat(data: dict) -> str:
    """The caveat on "run the exported script yourself", while one is owed.

    DEFECT-NEUTRAL ON PURPOSE, and this is the whole design of the function.
    Unlike CASE_CAUSE and CASE_STATUS it is *not* keyed by case id: it fires
    for any export-path finding on any case, so any sentence here describing a
    particular mechanism ("cells `read.csv` reads as missing", "a fix is
    planned") would be republished, unreviewed, the first time an unrelated
    export-path finding appears on an unrelated case. It carried exactly such a
    paragraph until 2026-07-28 — written for `issues/02`, left behind when that
    defect was fixed, and by then describing behaviour the app no longer had.

    So it says only what findings.json can prove: how many differences, on
    which cases, and where to read them. WHAT diverges and WHY belongs in the
    case's own narrative block, where CASE_CAUSE and CASE_STATUS are keyed by
    id and cannot leak onto a case they were not written for.

    The standing fact that a download *can* differ from the screen is not here
    either: it is unconditional prose in the same section, because it is true
    on a green page too and must not vanish with the last finding.
    """
    export_cases = [(c, _export_path_findings(c)) for c in data["cases"]]
    export_cases = [(c, f) for c, f in export_cases if f]
    if not export_cases:
        return ""
    ids = ", ".join(c["id"] for c, _ in export_cases)
    n = sum(len(f) for _, f in export_cases)
    where = ("one of the datasets on this page" if len(export_cases) == 1
             else f"{len(export_cases)} of the datasets on this page")
    return (
        "<div class=\"warn-box\">"
        f"<p><b>Right now, that first step has a caveat.</b> On {where} "
        f"(<code>{esc(ids)}</code>) the downloaded <code>.R</code> does not "
        f"reproduce the app it came from: "
        f"{n} difference{'s' if n != 1 else ''} "
        f"{'are' if n != 1 else 'is'} <a href=\"#differences\">published "
        f"above</a>, quantity by quantity, each with whatever this page knows "
        f"about that case. Read them before treating a downloaded script for "
        f"the same analysis as a confirmation of what you saw on screen. Every "
        f"other case's script reproduces the app exactly.</p></div>")


def build_web(findings_path: Path | str | None = None,
              out_path: Path | str | None = None,
              web_dir: Path | str | None = None,
              cases_dir: Path | str | None = None) -> Path:
    """Write web/validation.html — the page a user reads."""
    findings_path = (Path(findings_path) if findings_path
                     else RESULTS / "findings.json")
    results_dir = findings_path.parent
    out_path = Path(out_path) if out_path else WEB_PAGE
    web_dir = Path(web_dir) if web_dir else WEB
    cases_dir = Path(cases_dir) if cases_dir else CASES

    if not findings_path.exists():
        raise SystemExit(
            f"validation page: no findings to publish ({findings_path} does "
            "not exist). compare.py writes it before it returns, so its "
            "absence means the comparator did not finish.")
    data = json.loads(findings_path.read_text())
    pending = _pending(data, results_dir)
    findings_count = data["total_findings"]

    lede_tail = (
        f"This page is that comparison &mdash; including the "
        f"{findings_count} difference{'s' if findings_count != 1 else ''} it "
        f"currently finds." if findings_count else
        "This page is that comparison, including every difference it finds.")

    # THE SCOPE OF EVERY CLAIM ON THIS PAGE, COMPUTED RATHER THAN WRITTEN DOWN.
    # The comparison covers the registered cases and nothing else — not the
    # file a reader is about to upload — so the lede and the meta description
    # both say how many there are, from the same denominator the tiles use. A
    # ninth case must not leave either of them saying "eight".
    case_count = len(data["cases"]) + len(pending)
    case_word = _count_word(case_count)

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Statistical validation &mdash; Figura</title>
<meta name="description" content="How Figura's numbers are checked: on
{case_word} fixed test datasets its statistics are re-derived from the same raw
CSV by a second Python implementation, built from a written spec rather than
from Figura's R, with every difference published and each comparison's limits
named.">
<link rel="stylesheet" href="styles.css">
<style>{WEB_CSS}</style>
</head>
<body>
<header class="toolbar">
  <a class="brand brand-link" href="index.html">
    <svg class="mark" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <rect x="1" y="9" width="3" height="6" />
      <rect x="6" y="5" width="3" height="10" />
      <rect x="11" y="1" width="3" height="14" />
    </svg>
    <span class="wordmark">Figura</span>
  </a>
  <a class="back-link" href="index.html">&larr; Back to the app</a>
</header>

<main class="doc">
<article class="card">

<p class="eyebrow">Published evidence</p>
<h1>Statistical validation</h1>
<p class="lede">On {case_word} fixed test datasets, the statistics Figura
reports are re-derived from the same raw CSV by a second implementation, written
separately from the one that ships. What each comparison covers, and what it
leaves out, is set out case by case in
<a href="#checked">what was checked, and what was not</a> &mdash; the claim is
about those {case_word} files, not about a file you upload. {lede_tail}</p>

<div class="claim">
<p><b>What was actually done, stated precisely.</b> One specification &mdash;
prose, transcribed from Figura's R sources by an agent with full source access
&mdash; was implemented a second time in Python by agents that never read the R,
against an acceptance suite whose expected values were computed in R. It is a
re-implementation from a written spec, not two blind implementations of a shared
problem statement.</p>
<p><b>That catches</b> implementation bugs, library-default mismatches and
arithmetic errors: the failure modes where a second author, writing independent
code from a written rule, lands somewhere different. Those are the numerous,
ordinary, expensive mistakes.</p>
<p><b>It cannot catch</b> a misreading baked into the specification itself. If
the spec described R's behaviour wrongly, both implementations reproduce the
same wrong thing and agree with each other. The specifications cite the R
sources line by line, they are in the repository at
<code>stats-validation/spec/</code>, and they are the thing to attack if you
want to attack this.</p>
<p>The full disclosure &mdash; everything the clean-room bundle contained, and
two episodes where information leaked into it, named by commit hash &mdash; is
in <code>stats-validation/README.md</code>. Nothing here is a claim of
independent certification, accreditation or regulatory clearance: Figura is not
a medical device, and this is a comparison you can re-run, not a validation
report in the regulatory sense.</p>
</div>

{_web_tiles(data, pending)}
{_web_verdict(data, pending)}

<ul class="toc">
<li><a href="#checked">What was checked, and what was not</a></li>
<li><a href="#differences">The differences, in plain language</a></li>
<li><a href="#webr">The browser runtime: webR against native R</a></li>
<li><a href="#yourself">How to check this yourself</a></li>
<li><a href="#howmade">How this page is produced</a></li>
</ul>

<h2 id="checked">What was checked, and what was not</h2>
<p>Each case below is a real CSV run end to end through the shipped app &mdash;
the same CSV parser, the same analysis, the same rendering &mdash; and then
again through the independent implementation. Three comparisons run on each: the
numbers <b>as displayed</b>, the underlying quantities <b>at full precision</b>,
and the <code>.R</code> script the app offers <b>for download</b>, re-run in R.</p>
{_web_coverage_table(data, cases_dir)}
<p>Two boundaries this table does not draw on its own. <b>Explore</b>, the plot
builder, has no case here: it reports no statistics of its own, only a figure.
And the whole table above is <b>native R</b> &mdash; the runtime that actually
runs in your browser is checked separately, and how much of the roster that
check reaches is stated where it is reported; see
<a href="#webr">webR against native R</a>.</p>

<h3>Case by case</h3>
{_web_case_table(data, pending, cases_dir)}

<h2 id="differences">The differences, in plain language</h2>
{_web_differences_section(data)}

<h2 id="webr">The browser runtime: webR against native R</h2>
<p>Everything above ran native R on a developer machine. You do not run native
R &mdash; you run R compiled to WebAssembly, in your own browser tab. wasm has
no 80-bit extended precision, and webR ships reference linear-algebra libraries
rather than the platform's tuned ones, so an iteratively fitted model &mdash;
Cox's Newton-Raphson, logistic regression's IRLS &mdash; is where a difference
would show up if there were one.</p>
<p>A hand-run gate drives the real interface in a real browser (upload the file,
map the columns, confirm the event value, set the reference levels, tick the
variables, render) and compares every string the app displays against native R's
output: the tables cell by cell, and the analyses that report a sentence rather
than a table sentence by sentence. It is run before a release rather than on
every change, because it needs a browser and the network.</p>
{_web_webr_section(results_dir, web_dir)}

<h2 id="yourself">How to check this yourself</h2>
<p>You do not have to take this page's word for any of it.</p>
<ul>
<li><b>Re-run your own analysis in R.</b> Run it in Figura, then press
<code>.R</code> in the Console pane's toolbar. Figura downloads the exact script
it just ran &mdash; the statistical calls are the expressions the app evaluated,
not a rewrite of them. Run that script in your own R, or hand it to your
statistician, and compare it against what the app showed you.</li>
<li><b>Re-run this whole comparison.</b> From a checkout of the repository,
<code>make -C stats-validation all</code> re-derives every number on this page
from the raw CSVs and rewrites the evidence files. It needs R, Python and
Node.</li>
</ul>
<p class="aside">A standing note on that first step, true whether or not this
page is publishing a difference today. Figura parses your CSV in the browser and
never calls R's <code>read.csv</code>, so the downloaded script is
<i>generated</i> to read the file the same way the app read it &mdash; the same
trimming, the same treatment of a blank cell and of the two letters
<code>NA</code> typed as text. That is a parity that has to be maintained rather
than a property that holds by construction, which is why it is checked here on
all {case_word} datasets. One narrow divergence is known and still open: a
Kaplan&ndash;Meier script recodes a numeric status column slightly more
permissively than the app does, and no case on this page exercises it. It is
written up in
<code>stats-validation/issues/02-app-vs-exported-script-missing-values.md</code>.</p>
{_web_download_caveat(data)}

<h2 id="howmade">How this page is produced</h2>
<p>This page is generated from <code>stats-validation/results/findings.json</code>
&mdash; the comparator's own output &mdash; by
<code>stats-validation/build_scorecard.py --web</code>. It performs no
computation of its own and reads nothing but files in the repository, so the
same commit always renders the same page. Continuous integration regenerates it
on every push and fails the build if the published page is not what the current
evidence renders, which is what stops it from quietly ageing into a claim
nobody re-checked.</p>
<p>The evidence it is built from is in the repository beside it: the raw cases
(<code>stats-validation/cases/</code>), the written specifications
(<code>stats-validation/spec/</code>), the independent implementation
(<code>stats-validation/python/</code>) with each module's record of the
ambiguities its author hit, the comparator
(<code>stats-validation/compare/</code>), and the results
(<code>stats-validation/results/</code>).</p>

<footer class="doc-foot">
<p>Figura runs entirely in your browser: there is no backend that could receive
your data, and this page adds none. It loads the app's own stylesheet and
self-hosted fonts. Cloudflare, which serves the site, injects its Web
Analytics beacon at the edge (a page-load count with referrer, country and
device type; no uploaded research data or analysis results) &mdash; see <a href="about/">About</a>.</p>
<p><a href="index.html">Back to the app</a></p>
</footer>

</article>
</main>
</body>
</html>
"""
    out_path.write_text(doc)
    return out_path


if __name__ == "__main__":
    # Bare invocation writes BOTH artifacts, deliberately: they are two
    # renderings of one findings.json, and a run that refreshed the internal
    # scorecard while leaving the published page a release behind is exactly
    # the failure the freshness gate exists to make impossible.
    args = sys.argv[1:]
    if args and args != ["--web"]:
        raise SystemExit("usage: build_scorecard.py [--web]")
    if not args:
        print(f"wrote {build()}")
    print(f"wrote {build_web()}")
