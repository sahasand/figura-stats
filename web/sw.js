// web/sw.js
// Figura service worker: makes repeat visits fast by caching the app shell and
// the (no-cache) webR runtime. Three strategies, chosen by `routeFor` below:
//   R/*.R        network-first  — statistics may never be stale, even once
//   same-origin  stale-while-revalidate — chrome self-heals within a round trip
//   webR static  cache-first    — the ~6MB runtime is the bandwidth win
// Versioned: bump CACHE to hard-reset all caches on activate. Since R sources
// are network-first, the bump is a convenience lever, not the guard standing
// between a deploy and wrong output.
// SAFETY: only same-origin GETs and webR-origin STATIC assets are intercepted;
// everything else (non-GET, other origins, webR channel comms) passes straight
// through, so the SW can never disturb how webR loads or communicates.
const CACHE = "figura-v8";

// Resolve a scope-relative path against the SW's registration scope, so the
// precache/match paths are correct under a GitHub Pages PROJECT subpath
// (e.g. https://<user>.github.io/figura-stats/) as well as at root. Root-absolute
// paths ("/index.html") would 404 under a subpath and reject the all-or-nothing
// install, leaving the SW inert in production.
const scoped = (p) => new URL(p, self.registration.scope).toString();

// Minimal critical shell precached (scope-relative) so the app boots on a
// repeat/offline visit; everything else same-origin (guided modules, lib, R
// sources) lands in the cache the first time it's fetched via SWR below. The
// scope root itself is runtime-cached on first same-origin visit; the offline
// nav fallback matches scoped("index.html").
const PRECACHE = [
  "index.html", "app.js", "worker.js", "styles.css", "export-ui.js",
  "fonts/ibm-plex-sans-latin-400-normal.woff2",
  "fonts/ibm-plex-sans-latin-600-normal.woff2",
  "fonts/ibm-plex-mono-latin-400-normal.woff2",
  // Source Serif 4 sets the rendered artifact (table labels, captions, the
  // wordmark) — a late-arriving serif reflows the galley proof, so precache it.
  "fonts/source-serif-4-latin-400-normal.woff2",
  "fonts/source-serif-4-latin-600-normal.woff2",
];

// webR origins whose STATIC runtime/package assets we cache. Only these exact
// extensions are intercepted cross-origin — webR channel comms (which don't end
// in a static-asset extension) fall through untouched.
const WEBR_ORIGINS = ["https://webr.r-wasm.org", "https://repo.r-wasm.org"];
const STATIC_EXT = /\.(wasm|data|mjs|tgz|so)$/i;

// R sources are the statistical source of truth, not chrome. Stale CSS is a
// cosmetic blip that self-heals; stale R means the user reads numbers and
// figures produced by code this project has already decided was wrong, for a
// whole session. They get network-first below, which makes the CACHE bump a
// convenience again rather than the only thing standing between a deploy and
// wrong output. Matched on the path so a query string can't smuggle one past.
//
// THIRD-CACHE WARNING. Two caches are handled here — the service-worker cache
// (network-first below) and the browser's HTTP cache (`cache: "reload"` on that
// fetch). A CDN in front of the origin is a third one, and neither guard
// reaches it: `cache: "reload"` instructs the *browser*, not an edge. Today
// GitHub Pages serves this directly, so there is no third cache. If the site
// ever moves behind a CDN (e.g. a custom domain proxied through Cloudflare),
// add an explicit bypass-cache rule for `/R/*` at the edge BEFORE cutting the
// domain over. Cloudflare caches by file extension by default and `.R` is not
// on that list, so it works accidentally — until someone enables "Cache
// Everything" or a broad cache rule, at which point stale statistics come back
// wearing a new hat. Make it a rule, not an accident. See
// `.scratch/logistic-regression/issues/10-sw-serves-stale-r-sources.md`.
const R_SOURCE = /\/R\/[^/]+\.R$/i;

// The single routing decision, as a pure function of the request — the fetch
// handler below only dispatches on its answer. Kept separate so the choice
// that matters for correctness is directly testable (see web/sw.test.mjs);
// a service worker's routing is otherwise reachable only from a real browser.
function routeFor(req) {
  if (req.method !== "GET") return "pass";
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    return R_SOURCE.test(url.pathname) ? "r-source" : "same-origin";
  }
  if (WEBR_ORIGINS.includes(url.origin) && STATIC_EXT.test(url.pathname)) {
    return "webr-static";
  }
  return "pass";
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(PRECACHE.map(scoped)))
      .then(() => self.skipWaiting())   // take over promptly on update
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  switch (routeFor(req)) {
    case "r-source":                                   // statistics: never stale
      return event.respondWith(networkFirst(req));
    case "same-origin":
      return event.respondWith(staleWhileRevalidate(req)); // self-healing: never serves stale forever
    case "webr-static":
      return event.respondWith(cacheFirst(req));       // 6MB runtime: cache-first is the bandwidth win
    default:
      return;                                          // webR channel comms, other origins — untouched
  }
});

// Network-first, for R/*.R only. The cached copy exists purely so the app still
// works offline; whenever the network answers, its copy wins and replaces the
// cache. A few tens of KB of R next to the ~6MB runtime makes the bandwidth
// cost of never trusting the cache here negligible.
//
// `cache: "reload"` is load-bearing, not belt-and-braces: the browser's HTTP
// cache sits in FRONT of this fetch, and a response with no Cache-Control gets
// heuristic freshness (~10% of its age), so skipping only the service-worker
// cache still serves superseded statistics. Verified in a browser — a
// just-edited R file kept reading stale until the request bypassed both.
async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(new Request(req, { cache: "reload" }));
    if (res && res.ok) {
      cache.put(req, res.clone()).catch(() => {});     // best-effort; quota errors non-fatal
      return res;
    }
    // A 404/500 means a broken deploy, not a reason to boot with no statistics:
    // prefer the last good copy, and never cache the error body.
    const hit = await cache.match(req);
    return hit || res;
  } catch (_) {
    const hit = await cache.match(req);                // offline: cached R is all we have
    return hit || Response.error();
  }
}

// Stale-while-revalidate for same-origin assets other than R sources (which go
// network-first above): serve the cached copy immediately if present, while a
// background fetch refreshes the cache for next time — so a redeployed asset
// self-heals within one round trip, no CACHE bump required. On a cache miss we
// await the network. Only res.ok responses are cached (same-origin is always a
// transparent response, so a real 404/500 is correctly excluded — never opaque
// here). The background fetch always has a .catch so it can't reject unhandled.
async function staleWhileRevalidate(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req);
  const network = fetch(req)
    .then((res) => {
      if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
      return res;
    })
    .catch(() => null);
  if (hit) return hit;                                  // return cached now; let network update run
  const res = await network;
  if (res) return res;
  // Offline and uncached: for a navigation, fall back to the shell.
  if (req.mode === "navigate") {
    const shell = await cache.match(scoped("index.html"));
    if (shell) return shell;
  }
  return Response.error();
}

// Cache-first for the cross-origin webR static runtime/packages: serve from
// cache when present, else fetch + store. The 6MB no-cache runtime is the
// bandwidth win, and a CACHE version bump is the hard reset. Opaque cross-
// origin responses (type "opaque", status 0 — no CORS) are accepted since
// they're the pre-filtered webR static assets and replay fine to their
// requester; res.ok is always false for opaque, so we can't rely on it alone.
async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res && (res.ok || res.type === "opaque")) {
      cache.put(req, res.clone()).catch(() => {});     // best-effort; quota errors non-fatal
    }
    return res;
  } catch (_) {
    return Response.error();
  }
}
