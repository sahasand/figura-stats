// web/sw.test.mjs
// The service worker decides, per request, whether a cached copy may answer.
// For R/*.R that decision is correctness-relevant: R sources are the
// statistical source of truth, so a cached copy answering while the network is
// reachable means the user sees numbers produced by code the project has
// already replaced. These tests run the REAL web/sw.js in a vm sandbox — not a
// copy of its logic — so the routing they pin is the routing that ships.
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const SW_SRC = readFileSync(
  fileURLToPath(new URL("./sw.js", import.meta.url)), "utf8");

const ORIGIN = "https://example.github.io";
const SCOPE = ORIGIN + "/figura-stats/";

// A minimal cache double: records puts, answers matches by request url.
function makeCache(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    store,
    match: async (req) => store.get(req.url) || undefined,
    put: async (req, res) => { store.set(req.url, res); },
    addAll: async () => {},
  };
}

// Boot sw.js in a sandbox. Returns the context, so top-level `function`
// declarations (routeFor, networkFirst, …) are reachable as context globals.
function loadSw({ cache = makeCache(), fetchImpl = async () => null } = {}) {
  const listeners = {};
  const requests = [];   // every Request the SW constructs, for assertions
  const ctx = {
    self: {
      addEventListener: (type, fn) => { listeners[type] = fn; },
      location: { origin: ORIGIN },
      registration: { scope: SCOPE },
      skipWaiting: () => {},
      clients: { claim: () => {} },
    },
    caches: { open: async () => cache, keys: async () => [], delete: async () => true },
    fetch: fetchImpl,
    Response: { error: () => ({ ok: false, isError: true }) },
    // Real SW `Request` semantics for the one thing we assert on: an init that
    // overrides the cache mode of the request it copies.
    Request: class {
      constructor(input, init = {}) {
        this.method = input.method || "GET";
        this.url = input.url || String(input);
        this.cache = init.cache || input.cache || "default";
        requests.push(this);
      }
      clone() { return this; }
    },
    URL, console,
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(SW_SRC, ctx);
  return { ctx, listeners, cache, requests };
}

const get = (url) => ({ method: "GET", url, clone: () => get(url) });
const body = (text) => ({ ok: true, text, clone: () => body(text) });

// ---- Routing -------------------------------------------------------------

{
  const { ctx } = loadSw();
  const route = (req) => ctx.routeFor(req);

  // R sources get their own branch, at the scope root and under a Pages subpath.
  assert.equal(route(get(ORIGIN + "/R/cox.R")), "r-source");
  assert.equal(route(get(SCOPE + "R/dispatch.R")), "r-source");
  assert.equal(route(get(SCOPE + "R/logistic.R?v=2")), "r-source",
    "a query string must not smuggle an R source past the rule");

  // Everything else same-origin keeps stale-while-revalidate.
  assert.equal(route(get(SCOPE + "app.js")), "same-origin");
  assert.equal(route(get(SCOPE + "styles.css")), "same-origin");
  assert.equal(route(get(SCOPE + "guided/cox/spec.js")), "same-origin");
  assert.equal(route(get(SCOPE + "R/README.md")), "same-origin",
    "living under R/ is not enough — only .R files are statistical source");

  // Cross-origin: webR's static runtime stays cache-first, comms pass through.
  assert.equal(route(get("https://webr.r-wasm.org/latest/R.bin.wasm")), "webr-static");
  assert.equal(route(get("https://repo.r-wasm.org/survival.tgz")), "webr-static");
  assert.equal(route(get("https://webr.r-wasm.org/latest/channel")), "pass");
  assert.equal(route(get("https://example.com/anything.js")), "pass");

  // Non-GET is never intercepted, whatever the path.
  assert.equal(route({ method: "POST", url: SCOPE + "R/cox.R" }), "pass");
  console.log("ok - routeFor sends R sources to their own branch");
}

// ---- Network-first for R sources ----------------------------------------

{
  // The bug this file exists for: a cached R source must NOT answer while the
  // network is reachable, even though the cache holds a (superseded) copy.
  const url = SCOPE + "R/cox.R";
  const cache = makeCache({ [url]: body("stale <- 1") });
  const { ctx } = loadSw({ cache, fetchImpl: async () => body("fresh <- 2") });

  const res = await ctx.networkFirst(get(url));
  assert.equal(res.text, "fresh <- 2", "network wins over a cached R source");
  assert.equal(cache.store.get(url).text, "fresh <- 2", "fresh copy replaces the cached one");
  console.log("ok - a cached R source never answers while the network is reachable");
}

{
  // Network-first is not enough on its own: the browser's HTTP cache sits in
  // front of the SW's own fetch, and with no Cache-Control header it applies
  // heuristic freshness — which reintroduces exactly the staleness this
  // routing exists to remove. Observed in a real browser: a just-edited R file
  // still read stale until the request bypassed the HTTP cache.
  const url = SCOPE + "R/cox.R";
  const { ctx, requests } = loadSw({ fetchImpl: async () => body("fresh <- 2") });

  await ctx.networkFirst(get(url));
  const sent = requests.find((r) => r.url === url);
  assert.ok(sent, "networkFirst must go through a Request it controls");
  assert.equal(sent.cache, "reload",
    "R sources must bypass the HTTP cache, not just the service-worker cache");
  console.log("ok - the R fetch bypasses the HTTP cache too");
}

{
  // Offline still has to work: fall back to whatever R we have.
  const url = SCOPE + "R/km.R";
  const cache = makeCache({ [url]: body("cached <- 1") });
  const { ctx } = loadSw({
    cache,
    fetchImpl: async () => { throw new Error("offline"); },
  });

  const res = await ctx.networkFirst(get(url));
  assert.equal(res.text, "cached <- 1", "offline falls back to the cached R source");
  console.log("ok - offline falls back to the cached R source");
}

{
  // A deploy that 404s an R file must not poison the cache with the error body;
  // the last good copy is still better than a dead app.
  const url = SCOPE + "R/summarize.R";
  const cache = makeCache({ [url]: body("good <- 1") });
  const { ctx } = loadSw({ cache, fetchImpl: async () => ({ ok: false, status: 404 }) });

  const res = await ctx.networkFirst(get(url));
  assert.equal(res.text, "good <- 1", "a 404 falls back to the last good copy");
  assert.equal(cache.store.get(url).text, "good <- 1", "an error response is never cached");
  console.log("ok - a failed R fetch does not poison the cache");
}

{
  // Nothing cached and offline: surface the failure rather than a bogus body.
  const { ctx } = loadSw({
    cache: makeCache(),
    fetchImpl: async () => { throw new Error("offline"); },
  });
  const res = await ctx.networkFirst(get(SCOPE + "R/explore.R"));
  assert.equal(res.isError, true, "uncached and offline is an error, not a silent empty body");
  console.log("ok - uncached and offline surfaces an error");
}

console.log("sw.test.mjs OK");
