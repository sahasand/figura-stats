// web/sw.js
// Figura service worker: makes repeat visits fast by caching the app shell and
// the (no-cache) webR runtime. Versioned — bump CACHE on any deploy to hard-
// reset all caches on activate. With stale-while-revalidate for same-origin
// assets (below) the bump is no longer load-bearing for correctness — it's just
// a hard reset lever; SWR self-heals a stale asset within one background fetch.
// SAFETY: only same-origin GETs and webR-origin STATIC assets are intercepted;
// everything else (non-GET, other origins, webR channel comms) passes straight
// through, so the SW can never disturb how webR loads or communicates.
const CACHE = "figura-v2";

// Resolve a scope-relative path against the SW's registration scope, so the
// precache/match paths are correct under a GitHub Pages PROJECT subpath
// (e.g. https://<user>.github.io/my-stats/) as well as at root. Root-absolute
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
];

// webR origins whose STATIC runtime/package assets we cache. Only these exact
// extensions are intercepted cross-origin — webR channel comms (which don't end
// in a static-asset extension) fall through untouched.
const WEBR_ORIGINS = ["https://webr.r-wasm.org", "https://repo.r-wasm.org"];
const STATIC_EXT = /\.(wasm|data|mjs|tgz|so)$/i;

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
  if (req.method !== "GET") return;                    // pass through
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin; // origin-only: correct under a subpath
  const isWebRStatic =
    WEBR_ORIGINS.includes(url.origin) && STATIC_EXT.test(url.pathname);
  if (sameOrigin) {
    event.respondWith(staleWhileRevalidate(req));      // self-healing: never serves stale forever
  } else if (isWebRStatic) {
    event.respondWith(cacheFirst(req));                // 6MB runtime: cache-first is the bandwidth win
  }
  // else: pass through (webR channel comms, other origins) — untouched.
});

// Stale-while-revalidate for same-origin assets (incl. R/*.R, the statistical
// source of truth): serve the cached copy immediately if present, while a
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
