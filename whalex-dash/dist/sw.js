// WhaleX Prime — Service Worker (يجعل المنصّة تطبيقاً قابلاً للتثبيت)
const CACHE = 'whalex-v2';

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

// ═══ Push Notifications — استقبال وعرض الإشعار (والتطبيق مغلق) ═══
self.addEventListener('push', (event) => {
  let data = { title: 'WhaleX Prime', body: 'إشعار جديد' };
  try {
    if (event.data) data = event.data.json();
  } catch (e) { /* */ }
  const options = {
    body: data.body || '',
    icon: '/icon-192.png',
    badge: '/badge-96.png',
    vibrate: [200, 100, 200],
    tag: 'whalex-' + Date.now(),
    data: data,
  };
  event.waitUntil(
    self.registration.showNotification(data.title || 'WhaleX Prime', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ('focus' in c) return c.focus();
      }
      if (clients.openWindow) return clients.openWindow('/');
    })
  );
});
