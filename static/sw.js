const CACHE_NAME = 'husayniyyah-cache-v5';
const STATIC_ASSETS = [
  '/static/css/variables.css',
  '/static/css/base.css',
  '/static/css/layout.css',
  '/static/css/components.css',
  '/static/css/pages.css',
  '/static/css/cards.css',
  '/static/css/responsive.css',
  '/static/css/dark-mode.css',
  '/static/vendor/bootstrap/css/bootstrap.rtl.min.css',
  '/static/vendor/bootstrap-icons/bootstrap-icons.min.css',
  '/static/vendor/bootstrap/js/bootstrap.bundle.min.js',
  '/static/vendor/fonts/tajawal.css',
  '/static/icons/icon-96.png',
  '/static/icons/icon-144.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-384.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-maskable.png',
  '/static/icons/apple-touch-icon.png',
  '/static/offline.html'
];

const PAGES_TO_CACHE = [
  '/onboarding',
  '/login',
  '/cart',
  '/favorites',
  '/market'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        cache.addAll(STATIC_ASSETS);
        return Promise.allSettled(
          PAGES_TO_CACHE.map(page =>
            fetch(page, {cache: 'no-store'})
              .then(response => {
                if (response.ok) cache.put(page, response);
              })
              .catch(() => {})
          )
        );
      })
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;

  if (request.method !== 'GET') return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => {
          return caches.match(request).then(cached => {
            if (cached) return cached;
            return caches.match('/static/offline.html');
          });
        })
    );
    return;
  }

  if (
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'image' ||
    request.destination === 'font'
  ) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) {
          fetch(request).then(response => {
            if (response.ok) {
              const clone = response.clone();
              caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
            }
          }).catch(() => {});
          return cached;
        }
        return fetch(request).then(response => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        });
      })
    );
    return;
  }

  event.respondWith(fetch(request));
});

// Push Notification Events
self.addEventListener('push', event => {
  let data = { title: 'إشعار جديد', message: 'لديك إشعار جديد', url: '/' };
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: 'إشعار جديد', message: event.data.text(), url: '/' };
    }
  }

  const options = {
    body: data.message,
    icon: data.icon || '/static/icons/icon-192.png',
    badge: data.badge || '/static/icons/icon-96.png',
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const urlToOpen = event.notification.data.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (let client of windowClients) {
        if ('focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
