// web/lib/route.js
// The URL hash carries analysis and stage ONLY — `#<analysis>/<stage>` — never
// inputs, filenames or results (web/guided/shell.js owns the stage half). This
// reads the analysis half once at load so a landing page can deep-link into
// the app; `known` is the rail's registry, so an unknown prefix is ignored.
export function analysisFromHash(hash, known) {
  const m = /^#(\w+)(?:\/\w+)?$/.exec(hash || "");
  return m && known.includes(m[1]) ? m[1] : null;
}
