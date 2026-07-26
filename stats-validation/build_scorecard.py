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

import html
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

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

from compare import DISPOSITIONS  # noqa: E402

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


def _webr_section(results_dir: Path) -> str:
    """Task 12 fills this in. Until webr-tier.json exists, render an honest
    empty state rather than fabricating a result or crashing."""
    path = results_dir / "webr-tier.json"
    if not path.exists():
        return (
            "<div class=\"webr-empty\">Not yet run for this release &mdash; "
            "webR parity checks land in Task 12.</div>"
        )
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return (
            "<div class=\"webr-empty\">webr-tier.json is present but could "
            "not be read as JSON.</div>"
        )
    return f"<div class=\"scroll\"><pre>{esc(json.dumps(raw, indent=2))}</pre></div>"


def build(findings_path: Path | str | None = None,
          out_path: Path | str | None = None) -> Path:
    findings_path = Path(findings_path) if findings_path else RESULTS / "findings.json"
    results_dir = findings_path.parent
    out_path = Path(out_path) if out_path else results_dir / "scorecard.html"

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
<h2>WebR tier</h2>
{_webr_section(results_dir)}
</main></body></html>"""

    out_path.write_text(doc)
    return out_path


if __name__ == "__main__":
    print(f"wrote {build()}")
