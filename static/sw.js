/* Service Worker for Claude Code UI — PWA Support (cache-v2) */

const CACHE_NAME = 'claude-code-ui-cache-v2';
const STATIC_ASSETS = [
    '/',
    '/static/style.css',
    '/static/manifest.json'
];

// Install event
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch((err) => {
                console.warn('Cache addAll error:', err);
                // Don't fail installation if some assets fail
            });
        })
    );
    self.skipWaiting();
});

// Activate event
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch event — Network first, fallback to cache
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Skip API calls — always network
    if (event.request.url.includes('/submit') ||
        event.request.url.includes('/task/') ||
        event.request.url.includes('/queue') ||
        event.request.url.includes('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Static assets — cache first, fallback to network
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request).then((response) => {
                // Cache successful responses
                if (response.ok) {
                    const cache = caches.open(CACHE_NAME);
                    cache.then((c) => c.put(event.request, response.clone()));
                }
                return response;
            });
        }).catch(() => {
            return caches.match('/');
        })
    );
});
