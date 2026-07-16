// web/sw.js
// Figura service worker: makes repeat visits fast by caching the app shell and
// the (no-cache) webR runtime. Versioned — bump CACHE on any deploy so old
// caches are purged on activate (clean invalidation; see activate handler).
// SAFETY: only same-origin GETs and webR-origin STATIC assets are intercepted;
// everything else (non-GET, other origins, webR channel comms) passes straight
// through, so the SW can never disturb how webR loads or communicates.
const CACHE = "figura-v1";

// Minimal critical shell precached so the app boots on a repeat/offline visit;
// everything else same-origin (guided modules, lib, R sources) is runtime
// cache-first below, so it lands in the cache the first time it's fetched.
const PRECACHE = [
  "/", "/index.html", "/app.js", "/worker.js", "/styles.css", "/export-ui.js",
  "/fonts/ibm-plex-sans-latin-400-normal.woff2",
  "/fonts/ibm-plex-sans-latin-600-normal.woff2",
  "/fonts/ibm-plex-mono-latin-400-normal.woff2",
];

// webR origins whose STATIC runtime/package assets we cache. Only these exact
// extensions are intercepted cross-origin — webR channel comms (which don't end
// in a static-asset extension) fall through untouched.
const WEBR_ORIGINS = ["https://webr.r-wasm.org", "https://repo.r-wasm.org"];
const STATIC_EXT = /\.(wasm|data|mjs|tgz|so)$/i;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
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
  const sameOrigin = url.origin === self.location.origin;
  const isWebRStatic =
    WEBR_ORIGINS.includes(url.origin) && STATIC_EXT.test(url.pathname);
  if (!sameOrigin && !isWebRStatic) return;            // pass through (webR comms, other origins)
  event.respondWith(cacheFirst(req));
});

// Cache-first: serve from cache when present, else fetch + store. Guards against
// poisoning the cache with error/network-failure responses. Opaque cross-origin
// responses (type "opaque", status 0 — no CORS) are accepted since they're the
// pre-filtered webR static assets and replay fine to their requester.
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
    // Offline and uncached: for a navigation, fall back to the shell.
    if (req.mode === "navigate") {
      const shell = await cache.match("/index.html");
      if (shell) return shell;
    }
    return Response.error();
  }
}
