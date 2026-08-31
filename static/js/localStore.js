/**
 * LocalStore - إدارة السلة والمفضلة والملف الشخصي محلياً مع مزامنة خادم
 * يعتمد على OfflineDB لتخزين بيانات المنتجات والمتاجر في IndexedDB
 */
const LocalStore = (function() {
    const CART_KEY = 'local_cart';
    const FAVORITES_KEY = 'local_favorites';
    const PRODUCTS_CACHE_KEY = 'local_products_cache';
    const PROFILE_KEY = 'local_profile';

    function getCart() {
        try {
            return JSON.parse(localStorage.getItem(CART_KEY)) || {};
        } catch (e) {
            return {};
        }
    }

    function setCart(cart) {
        localStorage.setItem(CART_KEY, JSON.stringify(cart));
    }

    function getFavorites() {
        try {
            return JSON.parse(localStorage.getItem(FAVORITES_KEY)) || { products: [], stores: [] };
        } catch (e) {
            return { products: [], stores: [] };
        }
    }

    function setFavorites(favs) {
        localStorage.setItem(FAVORITES_KEY, JSON.stringify(favs));
    }

    function getProductsCache() {
        try {
            return JSON.parse(localStorage.getItem(PRODUCTS_CACHE_KEY)) || {};
        } catch (e) {
            return {};
        }
    }

    function setProductsCache(cache) {
        localStorage.setItem(PRODUCTS_CACHE_KEY, JSON.stringify(cache));
    }

    function cacheProduct(product) {
        const cache = getProductsCache();
        cache[product.id] = {
            id: product.id,
            name: product.name,
            price: product.price,
            image: product.image || product.main_image || '',
            store_name: product.store_name || (product.store && product.store.name) || '',
            store_id: product.store_id || (product.store && product.store.id) || null
        };
        setProductsCache(cache);

        if (typeof OfflineDB !== 'undefined') {
            OfflineDB.saveProduct(product).catch(err => console.warn('OfflineDB saveProduct failed:', err));
        }
    }

    function cacheStores(stores) {
        if (typeof OfflineDB !== 'undefined' && Array.isArray(stores) && stores.length > 0) {
            OfflineDB.saveStores(stores).catch(err => console.warn('OfflineDB saveStores failed:', err));
        }
    }

    function cacheStore(store) {
        if (typeof OfflineDB !== 'undefined' && store) {
            OfflineDB.saveStore(store).catch(err => console.warn('OfflineDB saveStore failed:', err));
        }
    }

    function getProfile() {
        try {
            return JSON.parse(localStorage.getItem(PROFILE_KEY)) || null;
        } catch (e) {
            return null;
        }
    }

    function setProfile(profile) {
        localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    }

    function cacheProfile(user) {
        if (!user) return;
        setProfile({
            id: user.id,
            username: user.username,
            email: user.email,
            phone: user.phone || '',
            bio: user.bio || '',
            avatar: user.avatar || '',
            public_id: user.public_id || '',
            role: user.role || ''
        });
    }

    function updateCartBadges() {
        const cart = getCart();
        const count = Object.values(cart).reduce((sum, qty) => sum + qty, 0);
        document.querySelectorAll('.cart-badge').forEach(b => {
            b.textContent = count;
            if (count > 0) {
                b.classList.remove('d-none');
                b.classList.add('cart-badge-pulse');
            } else {
                b.classList.add('d-none');
                b.classList.remove('cart-badge-pulse');
            }
        });
    }

    async function syncPendingOrders() {
        if (!navigator.onLine || typeof OfflineDB === 'undefined') return;
        try {
            const pending = await OfflineDB.getAllPendingOrders();
            if (!pending || pending.length === 0) return;
            for (const order of pending) {
                try {
                    const csrfToken = window.csrfToken || '';
                    const response = await fetch(`/cart/checkout/${order.store_id}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRF-Token': csrfToken,
                            'Accept': 'application/json'
                        },
                        body: JSON.stringify({
                            items: order.items,
                            delivery_address: order.delivery_address,
                            latitude: order.latitude,
                            longitude: order.longitude
                        })
                    });
                    if (response.ok) {
                        await OfflineDB.deletePendingOrder(order.local_id);
                        console.log('تم إرسال طلب معلق بنجاح');
                    } else {
                        const data = await response.json().catch(() => ({}));
                        console.warn('فشل إرسال الطلب المعلق:', data.message || response.status);
                    }
                } catch (err) {
                    console.warn('خطأ في إرسال الطلب المعلق:', err);
                }
            }
        } catch (err) {
            console.warn('فشل جلب الطلبات المعلقة:', err);
        }
    }

    async function sync() {
        if (!navigator.onLine) return;
        // مزامنة السلة والمفضلة أولاً
        const cart = getCart();
        const favs = getFavorites();
        try {
            const csrfToken = window.csrfToken || '';
            await fetch('/api/cart/sync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({ cart })
            });
            await fetch('/api/favorites/sync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({ favorites: favs })
            });
            const profile = getProfile();
            if (profile) {
                await syncProfile(profile);
            }
        } catch (err) {
            console.log('Local sync failed:', err);
        }
        // مزامنة الطلبات المعلقة
        syncPendingOrders();
    }

    async function syncProfile(profile) {
        if (!navigator.onLine) return false;
        try {
            const csrfToken = window.csrfToken || '';
            const response = await fetch('/api/profile/sync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify(profile)
            });
            return response.ok;
        } catch (err) {
            console.log('Profile sync failed:', err);
            return false;
        }
    }

    function addToCart(productId, qty, productData) {
        const cart = getCart();
        const key = String(productId);
        cart[key] = (cart[key] || 0) + qty;
        setCart(cart);
        if (productData) {
            cacheProduct(productData);
        }
        updateCartBadges();
        sync();
    }

    function updateCart(productId, qty) {
        const cart = getCart();
        const key = String(productId);
        if (qty < 1) {
            delete cart[key];
        } else {
            cart[key] = qty;
        }
        setCart(cart);
        updateCartBadges();
        sync();
    }

    function removeFromCart(productId) {
        updateCart(productId, 0);
    }

    function toggleFavorite(type, id, itemData) {
        const favs = getFavorites();
        const key = type === 'product' ? 'products' : 'stores';
        const index = favs[key].indexOf(id);
        if (index > -1) {
            favs[key].splice(index, 1);
        } else {
            favs[key].push(id);
            if (itemData && type === 'product') {
                cacheProduct(itemData);
            } else if (itemData && type === 'store') {
                cacheStore(itemData);
            }
        }
        setFavorites(favs);
        sync();
    }

    function isFavorite(type, id) {
        const favs = getFavorites();
        const key = type === 'product' ? 'products' : 'stores';
        return favs[key].includes(id);
    }

    window.addEventListener('online', sync);
    if (document.readyState === 'complete') {
        sync();
    } else {
        window.addEventListener('load', sync);
    }

    return {
        getCart,
        setCart,
        getFavorites,
        setFavorites,
        getProductsCache,
        updateCartBadges,
        sync,
        syncProfile,
        addToCart,
        updateCart,
        removeFromCart,
        toggleFavorite,
        isFavorite,
        cacheProduct,
        cacheStores,
        cacheStore,
        getProfile,
        setProfile,
        cacheProfile
    };
})();
