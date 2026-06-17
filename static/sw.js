const CACHE = 'shipcrawler-v1';
const ASSETS = [
  '/',
  '/static/css/shipcrawler.css',
  '/static/js/shipcrawler-core.js',
  '/static/js/shipcrawler-ui.js',
  '/static/js/shipcrawler-sse.js',
  '/static/js/globe.js',
  '/static/manifest.json',
];

self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(cache) {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE; }).map(function(k) { return caches.delete(k); })
      );
    })
  );
});

self.addEventListener('fetch', function(e) {
  e.respondWith(
    caches.match(e.request).then(function(cached) {
      return cached || fetch(e.request);
    })
  );
});
