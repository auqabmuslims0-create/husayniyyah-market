import sys
import os
import secrets
import time
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix
from database import db
from flask_migrate import Migrate
import models
from werkzeug.security import generate_password_hash

load_dotenv()

from auth import auth_bp
from admin import admin_bp
from blueprints.api import api_bp
from blueprints.social import social_bp
from store_owner import store_bp
from delivery.routes import delivery_bp

from customer.market import market_bp
from customer.reels import reels_bp
from customer.stores import stores_bp
from customer.offers import offers_bp
from customer.services import services_bp
from customer.account import account_bp
from customer.cart import cart_bp

from notifications import notifications_bp

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.config['RATELIMIT_STORAGE_URI'] = 'memory://'
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "100 per hour"],
    enabled=not app.debug
)

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

csp_policy = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline' https://unpkg.com; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "font-src 'self'; "
    "connect-src 'self' https://*.tile.openstreetmap.org https://router.project-osrm.org https://server.arcgisonline.com https://res.cloudinary.com; "
    "media-src 'self' https://res.cloudinary.com; "
    "frame-src 'self'"
)
Talisman(app, content_security_policy=csp_policy, force_https=os.environ.get('FLASK_ENV') == 'production')

def get_secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    if os.environ.get('FLASK_ENV') != 'production':
        key_file = os.path.join(app.instance_path, '.secret_key')
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                return f.read().strip()
        key = secrets.token_hex(32)
        os.makedirs(app.instance_path, exist_ok=True)
        with open(key_file, 'w') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        return key
    raise RuntimeError('SECRET_KEY must be set in production environment')

app.config['SECRET_KEY'] = get_secret_key()

def get_jwt_secret_key():
    key = os.environ.get('JWT_SECRET_KEY')
    if key:
        return key
    if os.environ.get('FLASK_ENV') != 'production':
        key_file = os.path.join(app.instance_path, '.jwt_secret_key')
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                return f.read().strip()
        key = secrets.token_hex(32)
        os.makedirs(app.instance_path, exist_ok=True)
        with open(key_file, 'w') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        return key
    raise RuntimeError('JWT_SECRET_KEY must be set in production environment')

app.config['JWT_SECRET_KEY'] = get_jwt_secret_key()

# ====== معالجة DATABASE_URL بشكل آمن ======
database_url = os.environ.get('DATABASE_URL')

if database_url:
    database_url = database_url.strip()
    # استبدال postgres:// بـ postgresql:// لتفادي مشاكل SQLAlchemy
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    # إذا كان الرابط لا يحتوي على منفذ واضح، نضيف المنفذ الافتراضي 5432
    parsed = urlparse(database_url)
    if parsed.scheme in ('postgresql', 'postgres') and parsed.port is None:
        # إعادة بناء الرابط مع المنفذ الافتراضي 5432
        host = parsed.hostname or ''
        netloc = f"{host}:5432"
        if parsed.username:
            userinfo = f"{parsed.username}"
            if parsed.password:
                userinfo += f":{parsed.password}"
            netloc = f"{userinfo}@{netloc}"
        database_url = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
else:
    # في حال عدم وجود DATABASE_URL نستخدم SQLite محليًا
    database_url = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'husayniyyah.db')

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
migrate = Migrate(app, db)

# تسجيل Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(store_bp)
app.register_blueprint(delivery_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(social_bp)

app.register_blueprint(market_bp)
app.register_blueprint(reels_bp)
app.register_blueprint(stores_bp)
app.register_blueprint(offers_bp)
app.register_blueprint(services_bp)
app.register_blueprint(account_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(notifications_bp)

@app.cli.command("create-admin")
def create_admin_command():
    """إنشاء المدير الافتراضي إذا لم يكن موجوداً."""
    ensure_admin()

def ensure_admin():
    # ضمان وجود الجداول قبل أي استعلام
    with app.app_context():
        db.create_all()
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_email = os.environ.get('ADMIN_EMAIL')
        admin_phone = os.environ.get('ADMIN_PHONE')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        if not all([admin_username, admin_email, admin_phone, admin_password]):
            app.logger.warning('لم يتم توفير بيانات المدير عبر .env، تخطي الإنشاء التلقائي.')
            return

        admin = models.User.query.filter_by(role='admin').first()
        if not admin:
            admin = models.User(
                username=admin_username,
                email=admin_email,
                phone=admin_phone,
                password_hash=generate_password_hash(admin_password),
                role='admin',
                is_active=True,
                public_id=secrets.token_hex(4).upper()
            )
            db.session.add(admin)
            db.session.commit()
            print("تم إنشاء المدير الافتراضي.")
        else:
            print("المدير موجود بالفعل.")

@app.before_request
def before_request_checks():
    if not request.path.startswith('/api/'):
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_hex(16)
        if request.method == 'POST':
            token = session.get('_csrf_token')
            request_token = request.headers.get('X-CSRF-Token') or request.form.get('_csrf_token')
            if not token or not request_token or token != request_token:
                abort(400, description='CSRF token مفقود أو غير صالح')

    g.user = None
    if 'user_id' in session:
        g.user = db.session.get(models.User, session['user_id'])

    if request.path.startswith('/api/') or request.endpoint is None:
        return

    if request.path == '/.well-known/assetlinks.json':
        return

    public_endpoints = [
        'auth.login', 'auth.register', 'auth.forgot_password', 'auth.confirm_identity',
        'auth.reset_password', 'auth.show_public_id', 'static',
        'market.home', 'market.market', 'market.search', 'market.search_suggestions',
        'stores.stores_page', 'stores.store_public', 'stores.product_public',
        'offers.offers_page', 'reels.reels', 'services.services_page', 'services.contact',
        'about', 'onboarding'
    ]
    if g.user is None:
        if request.endpoint not in public_endpoints:
            flash('يجب تسجيل الدخول أولاً')
            return redirect(url_for('auth.login'))

_notifications_cache = {}
_offers_cache = {}
CACHE_TIMEOUT = 30

@app.context_processor
def inject_notifications_count():
    if request.path.startswith('/api/') or request.path.startswith('/static/'):
        return dict(unread_notifications=0)
    if g.user is None:
        return dict(unread_notifications=0)

    user_id = g.user.id
    current_time = time.time()
    cached = _notifications_cache.get(user_id)
    if cached and (current_time - cached['timestamp'] < CACHE_TIMEOUT):
        return dict(unread_notifications=cached['count'])

    from shared.services.notification_service import NotificationService
    unread_count = NotificationService.get_unread_count(user_id)
    _notifications_cache[user_id] = {'count': unread_count, 'timestamp': current_time}
    return dict(unread_notifications=unread_count)

@app.context_processor
def inject_offers_count():
    if request.endpoint not in ['market.market', 'offers.offers_page', 'stores.stores_page']:
        return dict(offers_count=0)

    current_time = time.time()
    cached = _offers_cache.get('global')
    if cached and (current_time - cached['timestamp'] < CACHE_TIMEOUT):
        return dict(offers_count=cached['count'])

    offer_count = models.Product.query.filter_by(is_offer=True).count()
    _offers_cache['global'] = {'count': offer_count, 'timestamp': current_time}
    return dict(offers_count=offer_count)

@app.context_processor
def inject_current_user():
    return dict(current_user=g.user)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=session.get('_csrf_token', ''))

@app.context_processor
def inject_show_bottom_nav():
    show_bottom_nav = False
    endpoint = request.endpoint

    if g.user and g.user.role == 'customer':
        allowed_customer_endpoints = [
            'market.market',
            'reels.reels',
            'cart.cart',
            'offers.offers_page',
            'stores.stores_page',
            'stores.store_public',
            'stores.product_public',
            'notifications.notifications',
            'account.favorites'
        ]
        if endpoint in allowed_customer_endpoints:
            show_bottom_nav = True
    elif g.user and g.user.role == 'owner':
        if endpoint == 'market.market':
            show_bottom_nav = True

    return dict(show_bottom_nav=show_bottom_nav)

@app.template_filter('format_price')
def format_price(value):
    try:
        return f"{float(value):,.0f}"
    except (ValueError, TypeError):
        return value

@app.template_filter('get_image_url')
def get_image_url(filename):
    if not filename:
        return ''
    if filename.startswith('http'):
        return filename
    if filename.startswith('uploads/'):
        return url_for('static', filename=filename)
    return url_for('static', filename='uploads/' + filename)

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

@app.route('/onboarding')
def onboarding():
    return render_template('onboarding.html')

@app.errorhandler(403)
def forbidden(e):
    return render_template('shared/error.html', code=403, message='غير مسموح بالوصول إلى هذه الصفحة'), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template('shared/error.html', code=404, message='الصفحة غير موجودة'), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.exception('حدث خطأ 500')
    return render_template('shared/error.html', code=500, message='حدث خطأ داخلي في الخادم، يرجى المحاولة لاحقاً'), 500

@app.route('/.well-known/assetlinks.json')
def assetlinks():
    return app.send_static_file('.well-known/assetlinks.json')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    ensure_admin()
    from scheduler import init_scheduler
    init_scheduler(app)
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)

# تشغيل المجدول عند استيراد التطبيق في بيئة الإنتاج (مثل gunicorn)
if os.environ.get('SCHEDULER_ENABLED') == '1':
    from scheduler import init_scheduler
    with app.app_context():
        init_scheduler(app)
