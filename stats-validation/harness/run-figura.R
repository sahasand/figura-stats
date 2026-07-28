# Path A, display precision. Reads a spec JSON, runs the real render_figure(),
# and writes the displayed cells plus the exported .R script.
#
# usage: Rscript stats-validation/harness/run-figura.R <id> <spec.json> <out.json>
# Run from the repo root so devtools::load_all() finds the package tree.
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L)
id <- args[[1]]; spec_path <- args[[2]]; out_path <- args[[3]]

devtools::load_all(quiet = TRUE)

spec_json <- paste(readLines(spec_path, warn = FALSE), collapse = "\n")
res <- jsonlite::fromJSON(render_figure(spec_json), simplifyVector = FALSE)

if (!isTRUE(res$ok)) {
  stop(sprintf("render_figure failed for %s: %s", id, res$error))
}

jsonlite::write_json(
  list(id = id, text = res$text, code = res$code %||% NA_character_),
  out_path, auto_unbox = TRUE, pretty = TRUE
)
cat(sprintf("wrote %s\n", out_path))
