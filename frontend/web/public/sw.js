/* Kill-switch / cache-bust service worker.
 * Previous PWA builds left a controlling SW that could pin stale JS bundles
 * even after /sw.js itself was removed (SPA fallback HTML). This file:
 * 1) clears all Cache Storage entries
 * 2) unregisters itself
 * 3) asks open clients to reload once
 */
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys.map((k) => caches.delete(k)))
    await self.registration.unregister()
    const clients = await self.clients.matchAll({ type: 'window' })
    for (const client of clients) {
      client.navigate(client.url)
    }
  })())
})
