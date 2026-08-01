/* =============================================================================
   Seatback Cinema — service worker

   The whole point of this app is that it works on a plane, where there is
   either no connectivity or captive-portal Wi-Fi that resolves DNS but blocks
   everything. So the rule is: once the app has been opened on the ground, an
   offline launch must render the full catalog with posters — no spinners, no
   error states, nothing that needs the network.

   Caching strategy, by resource:
     app shell (html/js/icons), — stale-while-revalidate. Renders instantly
     catalog.json,                from cache — critical for the shell itself,
     last-updated.json            since that's what makes a fully-offline
                                 launch possible — then quietly refreshes in
                                 the background so the *next* launch picks up
                                 whatever changed, with no version string to
                                 remember to bump: every fetch re-checks the
                                 network itself, so nothing can go stale
                                 forever the way a forgotten cache-first
                                 version bump can.
     posters (image.tmdb.org)  — cache-first, opportunistically pre-warmed (see
                                 WARM_POSTERS below). Cross-origin, so responses
                                 may be opaque; that's fine for <img>.

   Single stable cache names below (no version suffix) — nothing here is ever
   bulk-invalidated by a deploy; staleness is handled per-request instead.
   ============================================================================= */

const SHELL_CACHE   = 'seatback-shell';
const DATA_CACHE    = 'seatback-data';
const POSTER_CACHE  = 'seatback-posters';

// Relative paths so this works both at a domain root and under a GitHub Pages
// project subpath (e.g. /seatback-cinema/).
const SHELL_ASSETS = [
  './',
  './index.html',
  './scoring.js',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './apple-touch-icon.png',
];

const CATALOG_PATH = 'catalog.json';
const LAST_UPDATED_PATH = 'last-updated.json';

// --- install: precache the shell ---------------------------------------------
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    // addAll() is atomic — one 404 would throw away the whole precache, and a
    // missing optional icon shouldn't cost us offline support. Cache
    // individually and tolerate misses.
    await Promise.all(SHELL_ASSETS.map(async (url) => {
      try { await cache.add(new Request(url, { cache: 'reload' })); }
      catch (e) { console.warn('[sw] shell asset skipped:', url, e.message); }
    }));
    // Also seed the catalog (+ its last-updated sidecar) so a first offline
    // launch has data. Tolerate the sidecar being briefly missing — it's a
    // display nicety, not something offline launch depends on.
    const dataCache = await caches.open(DATA_CACHE);
    try { await dataCache.add(new Request(CATALOG_PATH, { cache: 'reload' })); }
    catch (e) { console.warn('[sw] catalog precache skipped:', e.message); }
    try { await dataCache.add(new Request(LAST_UPDATED_PATH, { cache: 'reload' })); }
    catch (e) { console.warn('[sw] last-updated precache skipped:', e.message); }
    self.skipWaiting();
  })());
});

// --- activate: drop any caches left over from an older SW design --------------
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keep = new Set([SHELL_CACHE, DATA_CACHE, POSTER_CACHE]);
    const names = await caches.keys();
    await Promise.all(names.map(n => keep.has(n) ? null : caches.delete(n)));
    await self.clients.claim();
  })());
});

// --- fetch strategies --------------------------------------------------------
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request, { ignoreSearch: true });
  // 'reload' bypasses the browser's own HTTP cache for this fetch — without
  // it, an unbusted fetch() can be silently satisfied from HTTP cache instead
  // of reaching the network, defeating the "revalidate" half of this and
  // leaving stale content cached indefinitely despite this function's intent.
  const network = fetch(new Request(request, { cache: 'reload' }))
    .then((res) => { if (res && res.ok) cache.put(request, res.clone()); return res; })
    .catch(() => null);
  // Serve cache immediately when we have it; otherwise wait on the network.
  return cached || (await network) || new Response('[]', { headers: { 'Content-Type': 'application/json' } });
}

async function networkFirst(request, cacheName, timeoutMs) {
  const cache = await caches.open(cacheName);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(request, { signal: controller.signal });
    clearTimeout(timer);
    if (res && res.ok) cache.put(request, res.clone());
    return res;
  } catch (e) {
    clearTimeout(timer);
    const cached = await cache.match(request, { ignoreSearch: true });
    return cached || new Response('[]', { headers: { 'Content-Type': 'application/json' } });
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request, { ignoreSearch: true });
  if (cached) return cached;
  try {
    const res = await fetch(request);
    if (res && (res.ok || res.type === 'opaque')) cache.put(request, res.clone());
    return res;
  } catch (e) {
    return cached || Response.error();
  }
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Posters (cross-origin TMDB images)
  if (/(^|\.)image\.tmdb\.org$/.test(url.hostname)) {
    event.respondWith(cacheFirst(req, POSTER_CACHE));
    return;
  }

  // Same-origin only from here
  if (url.origin !== self.location.origin) return;

  // Catalog data (+ its last-updated sidecar). Normally stale-while-
  // revalidate (instant from cache, quiet background refresh) — but the
  // refresh button and the resume-from-background recheck (see index.html)
  // send X-Seatback-Refresh to explicitly ask for network-first instead,
  // since stale-while-revalidate would just hand back the same cached
  // response those callers are trying to bypass. Time-boxed so a captive-
  // portal Wi-Fi that resolves DNS but blocks traffic can't leave a manual
  // refresh hanging.
  const isDataPath = [CATALOG_PATH, LAST_UPDATED_PATH].some(
    (p) => url.pathname.endsWith('/' + p) || url.pathname.endsWith(p));
  if (isDataPath) {
    const forceRefresh = req.headers.get('X-Seatback-Refresh') === '1';
    event.respondWith(forceRefresh
      ? networkFirst(req, DATA_CACHE, 8000)
      : staleWhileRevalidate(req, DATA_CACHE));
    return;
  }

  // Navigations: serve the cached shell so an offline launch works, falling
  // back to the network (and then to the cached index) if needed. Scoped to
  // actual app-shell URLs only — otherwise every same-origin navigation
  // (e.g. curator.html, catalog-ops.html) would get hijacked into rendering
  // the passenger app instead of the page that was actually requested.
  const isShellNav = url.pathname.endsWith('/') || url.pathname.endsWith('/index.html');
  if (req.mode === 'navigate' && isShellNav) {
    event.respondWith((async () => {
      const cache = await caches.open(SHELL_CACHE);
      const cached = await cache.match('./index.html') || await cache.match('./');
      if (cached) {
        // 'reload' bypasses HTTP cache so this actually revalidates against
        // the network rather than potentially re-caching the same stale
        // response (see staleWhileRevalidate's comment above).
        fetch(new Request(req, { cache: 'reload' }))
          .then(res => { if (res && res.ok) cache.put('./index.html', res.clone()); }).catch(() => {});
        return cached;
      }
      try { return await fetch(req); }
      catch (e) { return new Response('Offline and no cached copy of the app yet.', { status: 503, headers: { 'Content-Type': 'text/plain' } }); }
    })());
    return;
  }

  // Everything else same-origin (js, icons). Stale-while-revalidate so a
  // changed file (a new commit, a regenerated icon) is picked up on the
  // *next* fetch — cache-first would keep serving byte-identical old
  // content forever since nothing here changes the cache's key.
  event.respondWith(staleWhileRevalidate(req, SHELL_CACHE));
});

// --- poster pre-warming ------------------------------------------------------
// The app posts its poster URLs once the catalog is loaded. If the passenger
// opens the app at the gate, every poster for the flight is cached before
// takeoff. Concurrency-limited so it never competes with the UI for bandwidth.
self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type !== 'WARM_POSTERS' || !Array.isArray(data.urls)) return;

  event.waitUntil((async () => {
    const cache = await caches.open(POSTER_CACHE);
    const urls = data.urls.filter(Boolean);
    let i = 0, warmed = 0;

    async function worker() {
      while (i < urls.length) {
        const url = urls[i++];
        try {
          if (await cache.match(url)) continue;       // already have it
          const res = await fetch(url, { mode: 'no-cors' });
          if (res && (res.ok || res.type === 'opaque')) { await cache.put(url, res.clone()); warmed++; }
        } catch (e) { /* offline or blocked — try again next launch */ }
      }
    }
    await Promise.all(Array.from({ length: 4 }, worker));   // 4 at a time
    console.log(`[sw] posters warmed: ${warmed}/${urls.length}`);
  })());
});
