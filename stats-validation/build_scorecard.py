"""findings.json -> a self-contained scorecard. No live computation.

Reads the exact shape compare.py's `main()` writes (verified against
stats-validation/compare/compare.py and a real stats-validation/results/
findings.json):

  {cases: [{id, kind, compared, passed, targets_met, targets: {...},
            findings: [{code, disposition, term, quantity, figura, python,
                        note}, ...]}, ...],
   total_compared, total_findings}

There is no top-level `targets` key — only per-case. Findings never carry
`code == "PASS"` (compare.py only appends non-pass findings; a passing case
has an empty `findings` list) and the taxonomy has no `EXACT_PASS` — that
code was considered and never wired to any emission (see compare.py's
DISPOSITIONS comment), so it is not styled here. The REAL emitted codes are:
PASS (synthesised here for a no-findings case row), DISPLAY_ARTIFACT, DEFECT,
COUNT_MISMATCH, DECISION_MISMATCH, SCRIPT_DIVERGENCE, MISSING_QUANTITY.
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
   did not. */
.PASS { color:var(--pass); }
.DISPLAY_ARTIFACT { color:var(--warn); }
.DEFECT,.COUNT_MISMATCH,.SCRIPT_DIVERGENCE,.MISSING_QUANTITY,
.DECISION_MISMATCH { color:var(--fail); font-weight:600; }
.targets-met { color:var(--pass); font-size:.78rem; white-space:nowrap; }
.targets-unmet { color:var(--fail); font-weight:600; font-size:.78rem; white-space:nowrap; }
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


def _tiles(data: dict) -> str:
    compared = data["total_compared"]
    findings = data["total_findings"]
    defects = sum(
        1 for c in data["cases"] for f in c["findings"]
        if f["code"] in DEFECT_CODES
    )
    cases = data["cases"]
    met = sum(1 for c in cases if c["targets_met"])
    return f"""<div class="tiles">
  <div class="tile"><b>{esc(compared)}</b><span>values compared</span></div>
  <div class="tile"><b>{esc(findings)}</b><span>differences</span></div>
  <div class="tile"><b>{esc(defects)}</b><span>defects</span></div>
  <div class="tile"><b>{met}/{len(cases)}</b><span>cases meet targets</span></div>
</div>"""


def _rows(data: dict) -> str:
    rows = []
    for c in data["cases"]:
        targets_class = "targets-met" if c["targets_met"] else "targets-unmet"
        targets_label = "targets met" if c["targets_met"] else "TARGETS UNMET"
        coverage_cell = f"<td class='{targets_class}'>{esc(targets_label)}</td>"
        if not c["findings"]:
            rows.append(
                f"<tr><td>{esc(c['id'])}</td><td class='PASS'>PASS</td>"
                f"{coverage_cell}"
                f"<td colspan='4'>{esc(c['compared'])} values compared, "
                f"no differences</td></tr>"
            )
            continue
        for f in c["findings"]:
            rows.append(
                f"<tr><td>{esc(c['id'])}</td>"
                f"<td class='{esc(f['code'])}'>{esc(f['code'])}</td>"
                f"{coverage_cell}"
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

    data = json.loads(findings_path.read_text())

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Figura statistical validation scorecard</title><style>{CSS}</style></head>
<body><main>
<h1>Statistical validation scorecard</h1>
<p class="sub">Every number Figura reports, re-derived by an independently
programmed Python implementation from the same raw CSV.</p>
{_tiles(data)}
<div class="scroll"><table>
<thead><tr><th>Case</th><th>Result</th><th>Coverage</th><th>Term</th>
<th>Quantity</th><th>Figura</th><th>Python</th></tr></thead>
<tbody>{_rows(data)}</tbody></table></div>
<p class="sub"><b>Coverage</b> ("targets met") means every quantity the case
declares in <code>exact_targets</code> was actually credited by a performed
comparison — a coverage failure marks a case TARGETS UNMET even if every
comparison that did run passed. <b>Display artifact</b> means both paths
computed the same number and only the rendered string differs, within half a
display step. <b>Defect</b> means the values themselves disagree beyond a
relative tolerance of 1e-6. <b>Missing quantity</b> means something expected
was never compared at all &mdash; a coverage failure, not a value
disagreement. <b>Script divergence</b> means the exported .R does not
reproduce what the screen showed. <b>Count mismatch</b> means the two paths
analysed different rows. <b>Decision mismatch</b> means the two paths chose
different summary statistics for a Table 1 variable &mdash; mean &plusmn; SD
where the other chose median (IQR), say &mdash; which is a defect even when
every number in the row is individually correct.</p>
<h2>WebR tier</h2>
{_webr_section(results_dir)}
</main></body></html>"""

    out_path.write_text(doc)
    return out_path


if __name__ == "__main__":
    print(f"wrote {build()}")
