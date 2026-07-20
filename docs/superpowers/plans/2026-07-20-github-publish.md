# Plan: Publish as public GitHub repo `figura-stats`

**Date:** 2026-07-20
**Decisions:** Public · `figura-stats` · MIT · push now (before logistic regression)
**Account:** `sahasand` (gh CLI authed, scopes `repo`, `workflow`)
**Resulting URLs:** repo `https://github.com/sahasand/figura-stats` · site `https://sahasand.github.io/figura-stats/`

---

## Pre-flight findings (already verified — no action)

| Check | Result |
|---|---|
| Existing remote | None. Fresh push, no merge/rebase risk. |
| History | 182 commits, single author `sandeep saha <san.saha@gmail.com>`. No rewrite needed. |
| Secrets in tracked files | None. Only match was `pages: write` in `deploy.yml`. |
| Bloat | 141 tracked files, ~1 MB. `node_modules/`, `web/R/`, `test-results/`, `.gstack/`, `.superpowers/` all correctly ignored. |
| Subpath safety | `index.html` has **no** root-absolute `src`/`href`; `sw.js` uses `scoped()` against registration scope. **Any repo name works with zero code changes.** |
| CI | `ci.yml` needs no secrets (R suite + JS unit). Will run green on first push. |

---

## Task 1 — Ignore machine-local and third-party-scraped directories

**Why:** `.firecrawl/` holds scraped journal pages (Red Journal, PMC) — third-party copyrighted content that must not be republished from a public repo. `.claude/` is a machine-local session lock.

Append to `.gitignore`:

```
# Local agent/session state and scraped third-party research sources —
# never publish (.firecrawl holds copyrighted journal page captures).
.claude/
.firecrawl/
```

**Verify:** `git status --short` no longer lists `.claude` or `.firecrawl`.

---

## Task 2 — Add MIT LICENSE

**Why:** README claims "free, open-source"; without a license file that is legally *all rights reserved* and nobody may fork, reuse, or cite-with-reuse. This is the only hard blocker to publishing.

Create `LICENSE` — standard MIT text, `Copyright (c) 2026 Sandeep Saha`.

**Verify:** GitHub detects it as MIT in the repo sidebar after push.

---

## Task 3 — Rewrite README for a public audience

**Why:** Current README says "**Two** guided analyses" — there are five. It is the front door of a public repo and is the single most-read file.

Rewrite to cover:
- Title **Figura**, one-line pitch, live-site link `https://sahasand.github.io/figura-stats/`
- **All five** guided analyses: Summary statistics (Table 1), Kaplan–Meier, Explore plot, Group comparison, Cox regression
- The no-egress guarantee stated plainly (it is the product's main differentiator)
- Journal-export capabilities (300/600/1200 dpi PNG with real `pHYs` stamp, SVG, `.tsv`, runnable `.R` script)
- Develop section, corrected: `rm -rf web/R && cp -R R web/R` **before** `npm run serve` / `npm run test:e2e` (current README omits the `rm -rf`, which nests the dir), `Rscript -e 'devtools::test()'`, `npm run test:unit`
- **Disclaimer:** research/manuscript-preparation tool, not for clinical decision-making; no warranty; users must verify results before publication
- License line

**Verify:** every analysis named in README matches a `data-figure` button in `web/index.html`.

---

## Task 4 — Sync the project name

**Why:** name currently differs across four files. Cosmetic only (confirmed no functional coupling), but incoherent in public.

- `package.json` → `"name": "figura-stats"`
- `web/sw.js:14` comment → `/figura-stats/` example path
- `TODOS.md`, `web/styles.css:705` → `~/.gstack/projects/my-stats/` paths are local design-asset references; leave as-is (accurate history, harmless)
- **`DESCRIPTION` `Package: manuscriptfigures` → leave unchanged.** That is the R package identity, legitimately distinct from the repo name, and renaming it touches `local::.` in CI for no gain.

**Verify:** `npm run test:unit` still green (`package.json` name is not referenced by any test).

---

## Task 5 — Commit the remaining untracked work

- `docs/superpowers/plans/2026-07-17-logistic-regression.md` — commit; matches the six already-tracked plans.
- `.scratch/` — commit. `CLAUDE.md` designates it the issue tracker ("Issues are tracked as local Markdown files under `.scratch/`"), and `CLAUDE.md` links `.scratch/guided-analysis-km/issues/stage-a-fast-follows.md`. Publishing without it leaves a dangling reference.
- `docs/research/` — **check before committing.** `2026-07-15-interactive-ggplot2-workflows.md` is own-synthesis (commit). `2026-07-16-uxpeak-design-intelligence-playbook.md` — read first; if it is largely quoted third-party material, gitignore it instead.

**Verify:** `git status --short` is empty.

---

## Task 6 — Create the repo and push

```
gh repo create figura-stats --public --source=. --remote=origin \
  --description "Clinical manuscript figures & statistics computed entirely in your browser via webR — no server, no data upload."
git push -u origin main
```

Then set discovery topics:

```
gh repo edit sahasand/figura-stats --add-topic \
  r,webr,webassembly,statistics,clinical-research,ggplot2,survival-analysis,biostatistics
```

**Verify:** `gh repo view sahasand/figura-stats --web`; confirm 182 commits and MIT badge.

---

## Task 7 — Enable GitHub Pages via Actions

`deploy.yml` uses `actions/deploy-pages@v4`, which requires the Pages **source** to be "GitHub Actions" — not set by default on a new repo, so the first deploy run will fail without this.

```
gh api -X POST repos/sahasand/figura-stats/pages \
  -f build_type=workflow || \
gh api -X PUT repos/sahasand/figura-stats/pages -f build_type=workflow
```

**Verify:** `gh run list --limit 5` shows CI and Deploy; both conclude `success`.

---

## Task 8 — Verify the live site end-to-end

Using the gstack `/browse` skill (per global instruction — never the Chrome MCP tools), load `https://sahasand.github.io/figura-stats/` and confirm:

1. Page renders with self-hosted IBM Plex fonts (no CDN font request)
2. All five nav buttons present
3. One analysis runs its demo to completion — proves webR boots and `fetch("R/*.R")` resolves **under the project subpath** (the single highest-risk difference between local and production)
4. Service worker registers; no console errors
5. Network panel shows requests only to `sahasand.github.io`, `webr.r-wasm.org`, `repo.r-wasm.org` — **the no-egress invariant, verified in production**

**If step 3 fails,** the cause is almost certainly a path resolving above the subpath root; check `web/worker.js`'s `R/` fetch base before anything else.

---

## Not doing (and why)

- **History rewrite / squash** — history is clean, single-author, secret-free. Rewriting would destroy an honest record of how the tool was built.
- **Branch protection on `main`** — solo repo; would only block your own direct pushes. Add if contributors arrive.
- **Playwright e2e in CI** — deliberately excluded already (downloads webR; slow and flaky). Unchanged by publishing.
- **Renaming the local folder** `~/Documents/my-stats` — the global working rule is one folder per theme; the folder stays, only the remote is named `figura-stats`.

---

## Execution order

Tasks 1–5 are local commits (safe, reversible). **Task 6 is the irreversible, outward-facing step** — everything before it is a normal working-tree change; everything from it on is public. Confirm before running Task 6.
