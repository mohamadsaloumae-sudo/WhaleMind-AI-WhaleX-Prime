// WhaleX Prime — Service Worker (يجعل المنصّة تطبيقاً قابلاً للتثبيت)
const CACHE = 'whalex-v1';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
  // تنظيف الكاش القديم
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
});

// نمرّر الطلبات للشبكة (لا نخزّن API — البيانات يجب أن تبقى حيّة)
self.addEventListener('fetch', (e) => {
  // لا نتدخّل في طلبات API أو WebSocket — تبقى حيّة دائماً
  if (e.request.url.includes('/api/') || e.request.url.includes('/ws')) {
    return;
  }
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
