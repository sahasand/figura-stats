"""findings.json -> a self-contained scorecard. No live computation.

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
   case fails its exact tier while its display tier passes, i.e. the numbers on
   screen were right and the exported .R was wrong, and a column headed
   "Figura" alone says the opposite.
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

from compare import DISPOSITIONS, PUBLISHED_SIGNIFICANT_DIGITS  # noqa: E402

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
   ABORTED (a structural precondition failure — e.g. a row-count mismatch)
   gets the same fail colour and weight as DRIFT — it is not a lesser
   problem, it is the harness saying the two runtimes disagreed on the SHAPE
   of the output before any cell was even compared — but italic, so it is
   never mistaken for a DRIFT verdict at a glance. */
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

    An ABORTED case (a structural precondition failure — e.g. a row-count
    mismatch, caught by e2e/compare-text.mjs's `runCase`) is rendered as its
    own distinct verdict, never silently absent. Before this existed, a
    precondition failure aborted the whole spec before webr-tier.json was ever
    written, so the single most alarming drift class — the two runtimes
    disagreeing on the SHAPE of the output — rendered identically to "never
    run" (the empty-state branch above). Distinguishing the two is the entire
    point of this branch.
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
                f"<td>Structural precondition failure &mdash; the two "
                f"runtimes disagreed on the shape of the output before any "
                f"cell was compared: {esc(c.get('reason'))}</td></tr>")
            continue
        identical = bool(c.get("identical"))
        cls = "webr-identical" if identical else "webr-drift"
        label = "IDENTICAL" if identical else "DRIFT"
        differing = c.get("differing_cells") or []
        compared = c.get("cells_compared")
        if identical:
            detail = (f"{esc(compared)} displayed cells matched native R "
                      "exactly")
        else:
            items = "".join(
                f"<li><b>{esc(d.get('term'))}</b> / {esc(d.get('column'))}: "
                f"native <code>{esc(d.get('native'))}</code> &rarr; "
                f"webR <code>{esc(d.get('webr'))}</code></li>"
                for d in differing)
            detail = (f"{len(differing)} of {esc(compared)} cells differ"
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

    return (
        f"{header_html}{staleness_html}{totals_html}"
        "<div class=\"scroll\"><table><thead><tr><th>Case</th>"
        "<th>Result</th><th>Cells compared</th><th>Detail</th></tr></thead>"
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
<p class="sub">Every number Figura reports, re-derived by an independently
programmed Python implementation from the same raw CSV.</p>
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


if __name__ == "__main__":
    print(f"wrote {build()}")
