const CACHE_NAME = 'husayniyyah-cache-v6';
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

// الصفحات العامة التي نسمح بتخزينها للعمل دون اتصال
const PUBLIC_PATHS = [
  '/',
  '/market',
  '/stores',
  '/offers',
  '/search',
  '/product/',
  '/store/'
];

// الصفحات الأساسية التي نريد تخزينها عند التثبيت
const PAGES_TO_CACHE = [
  '/',
  '/market',
  '/stores',
  '/offers',
  '/offline.html'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        // تخزين الأصول الثابتة
        cache.addAll(STATIC_ASSETS);
        // محاولة تخزين الصفحات العامة الأساسية
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

  // للصفحات (navigate) نستخدم Network First مع cache fallback
  if (request.mode === 'navigate') {
    // التحقق مما إذا كانت الصفحة عامة (يمكن تخزينها)
    const url = new URL(request.url);
    const isPublicPath = PUBLIC_PATHS.some(path => {
      if (path === '/') return url.pathname === '/';
      if (path.endsWith('/')) return url.pathname.startsWith(path);
      return url.pathname === path || url.pathname.startsWith(path);
    });

    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok && isPublicPath) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => {
          return caches.match(request).then(cached => {
            if (cached) return cached;
            // إذا لم توجد نسخة مخزنة، نعرض صفحة offline
            return caches.match('/static/offline.html');
          });
        })
    );
    return;
  }

  // للصور التي يرفعها المستخدمون (مثل الصور الرمزية) نستخدم Network First
  if (request.destination === 'image' && request.url.includes('/static/uploads/')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // للأصول الثابتة الأخرى نستخدم Cache First مع update في الخلفية
  if (
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'image' ||
    request.destination === 'font'
  ) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) {
          // تحديث في الخلفية
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

  // لأي طلب آخر نمرره مباشرة
  event.respondWith(fetch(request));
});
