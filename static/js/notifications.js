/**
 * notifications.js - إدارة صفحة الإشعارات (تصفية، اقتراع، تحديث عداد)
 */
document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('#notificationTabs .nav-link');
    const items = document.querySelectorAll('#notificationsList .notification-item');
    const notifCount = document.getElementById('notifCount');

    // تصفية
    tabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            const filter = this.dataset.filter;
            let visible = 0;
            items.forEach(item => {
                let show = true;
                if (filter === 'unread') {
                    show = item.dataset.read === 'false';
                } else if (filter !== 'all') {
                    show = item.dataset.type === filter;
                }
                if (show) {
                    item.style.display = '';
                    visible++;
                } else {
                    item.style.display = 'none';
                }
            });
            if (notifCount) {
                notifCount.textContent = visible + ' إشعار';
            }
        });
    });

    // اقتراع دوري لعداد غير المقروء (كل 30 ثانية) فقط عند الاتصال
    function pollUnreadCount() {
        if (!navigator.onLine) return; // لا تحاول عند عدم الاتصال
        fetch('/api/notifications/unread-count', {
            headers: { 'Accept': 'application/json' }
        })
        .then(res => res.json())
        .then(data => {
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                if (data.unread_count > 0) {
                    badge.textContent = data.unread_count;
                    badge.classList.remove('d-none');
                } else {
                    badge.textContent = '0';
                    badge.classList.add('d-none');
                }
            }
        })
        .catch(err => console.warn('Poll failed:', err));
    }

    // تشغيل الاقتراع فقط عند الاتصال، وإيقافه عند عدم الاتصال
    let pollInterval = null;

    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);
        if (navigator.onLine) {
            pollUnreadCount();
            pollInterval = setInterval(pollUnreadCount, 30000);
        }
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    window.addEventListener('online', startPolling);
    window.addEventListener('offline', stopPolling);

    startPolling();
});
