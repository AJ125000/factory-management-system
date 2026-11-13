/*
 * FMS service worker — keeps the app itself on the device, so it opens even when the
 * laptop (the hub) is switched off. Generated at build time by vite.config.ts, which
 * fills in VERSION and PRECACHE (the exact list of built files).
 *
 * - Pages:   try the laptop first (fresh app), fall back to the copy on the device.
 * - Files:   from the device copy (they have content hashes, so they never go stale).
 * - /api/*:  never touched here. Data is managed by the app (React Query + outbox).
 * - Updates: a new version waits until the owner taps "Update now" (no surprise reloads).
 */

const VERSION = __VERSION__;
const PRECACHE = __PRECACHE__;
const CACHE = `fms-app-${VERSION}`;

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      for (const key of await caches.keys()) {
        if (key.startsWith('fms-app-') && key !== CACHE) await caches.delete(key);
      }
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;
  event.respondWith(request.mode === 'navigate' ? pageFromHubOrDevice(request) : fileFromDevice(request));
});

async function pageFromHubOrDevice(request) {
  try {
    const response = await fetch(request, { signal: AbortSignal.timeout(4000) });
    // 502/503/504 = Tailscale is up but the FMS server isn't: use the device copy.
    if (response.ok) return response;
  } catch {
    /* laptop unreachable */
  }
  const cache = await caches.open(CACHE);
  return (await cache.match('/index.html')) || (await cache.match('/')) || Response.error();
}

async function fileFromDevice(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && new URL(request.url).pathname.startsWith('/assets/')) {
    const cache = await caches.open(CACHE);
    await cache.put(request, response.clone());
  }
  return response;
}
