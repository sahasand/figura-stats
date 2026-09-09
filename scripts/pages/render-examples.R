# Renders each demo spec in scripts/pages/.build/*.spec.json through the real
# render_figure() and writes web/<slug>/example.json = {svg, text}. Run from
# the repo root:  npm run build:examples
# The output is COMMITTED so the page generator (build.mjs) needs no R.
devtools::load_all(quiet = TRUE)
specs <- Sys.glob("scripts/pages/.build/*.spec.json")
stopifnot(length(specs) > 0)
for (sp in specs) {
  slug <- sub("\\.spec\\.json$", "", basename(sp))
  set.seed(20260909L)   # fig_summary and fig_groupcompare use unseeded geom_jitter; a fixed seed makes the committed render reproducible without changing app behaviour
  res <- jsonlite::fromJSON(render_figure(paste(readLines(sp, warn = FALSE), collapse = "\n")),
                            simplifyVector = FALSE)
  if (!isTRUE(res$ok)) stop(sprintf("render_figure failed for %s: %s", slug, res$error))
  dir.create(file.path("web", slug), showWarnings = FALSE)
  jsonlite::write_json(list(svg = res$svg, text = res$text),
                       file.path("web", slug, "example.json"),
                       auto_unbox = TRUE, pretty = TRUE)
  cat(sprintf("wrote web/%s/example.json\n", slug))
}
