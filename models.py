# ملاحظة: هذا الملف كامل كما كان مع إضافة الحقلين في كلاس Notification
from datetime import datetime
from database import db
from time_utils import current_time
from sqlalchemy import UniqueConstraint, CheckConstraint

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    avatar = db.Column(db.String(300), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    dark_mode = db.Column(db.Boolean, default=False)  # تفضيل الوضع الداكن
    role = db.Column(db.String(20), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    shift_start_time = db.Column(db.Time, nullable=True)
    shift_end_time = db.Column(db.Time, nullable=True)
    max_active_orders = db.Column(db.Integer, default=3)
    is_available = db.Column(db.Boolean, default=True)
    public_id = db.Column(db.String(20), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=current_time)

    stores = db.relationship('Store', back_populates='owner', cascade="all, delete-orphan")
    orders = db.relationship('Order', back_populates='customer', foreign_keys='Order.customer_id')
    reviews = db.relationship('Review', back_populates='user', cascade="all, delete-orphan")
    favorites = db.relationship('Favorite', back_populates='user', cascade="all, delete-orphan")
    notifications = db.relationship('Notification', back_populates='user', cascade="all, delete-orphan")
    subscriptions = db.relationship('Subscription', back_populates='user', foreign_keys='Subscription.user_id')
    product_comments = db.relationship('ProductComment', back_populates='user', cascade="all, delete-orphan")
    delivery_orders = db.relationship('Order', back_populates='delivery_person', foreign_keys='Order.delivery_person_id')
    cart_items = db.relationship('CartItem', back_populates='user', cascade="all, delete-orphan")
    payments = db.relationship('Payment', back_populates='user', cascade="all, delete-orphan")
    push_subscriptions = db.relationship('PushSubscription', back_populates='user', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String(300), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    working_hours = db.Column(db.String(100), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    has_delivery = db.Column(db.Boolean, default=False)
    subscription_status = db.Column(db.String(20), default='pending', index=True)
    subscription_expiry = db.Column(db.DateTime, nullable=True)
    pending_deletion_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=current_time)

    __table_args__ = (
        CheckConstraint(
            "subscription_status IN ('pending', 'active', 'suspended', 'cancelled')",
            name='ck_store_subscription_status_valid'
        ),
    )

    owner = db.relationship('User', back_populates='stores')
    products = db.relationship('Product', back_populates='store', cascade="all, delete-orphan")
    orders = db.relationship('Order', back_populates='store')
    categories = db.relationship('Category', back_populates='store', cascade="all, delete-orphan")
    subscriptions = db.relationship('Subscription', back_populates='store', foreign_keys='Subscription.store_id')
    cart_items = db.relationship('CartItem', back_populates='store', cascade="all, delete-orphan")
    payments = db.relationship('Payment', back_populates='store')

    def __repr__(self):
        return f'<Store {self.name}>'

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True, index=True)

    parent = db.relationship('Category', remote_side=[id], back_populates='children')
    children = db.relationship('Category', back_populates='parent')
    products = db.relationship('Product', back_populates='category')
    store = db.relationship('Store', back_populates='categories')

    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    product_code = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    is_offer = db.Column(db.Boolean, default=False, index=True)
    offer_price = db.Column(db.Float, nullable=True)
    original_price = db.Column(db.Float, nullable=True)  # السعر قبل الخصم إذا كان العرض مختلفًا
    offer_description = db.Column(db.Text, nullable=True)
    stock_quantity = db.Column(db.Integer, default=0)
    options = db.Column(db.Text, nullable=True)
    main_image = db.Column(db.String(300), nullable=True)
    sub_images = db.Column(db.Text, nullable=True)
    video = db.Column(db.String(300), nullable=True)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=current_time, index=True)

    __table_args__ = (
        CheckConstraint('price >= 0', name='ck_product_price_non_negative'),
        CheckConstraint('offer_price IS NULL OR offer_price >= 0', name='ck_product_offer_price_non_negative'),
        CheckConstraint('stock_quantity >= 0', name='ck_product_stock_non_negative'),
        db.Index('ix_product_store_created', 'store_id', 'created_at'),
        db.Index('ix_product_offer_created', 'is_offer', 'created_at'),
        db.Index('ix_product_store_offer', 'store_id', 'is_offer'),
    )

    store = db.relationship('Store', back_populates='products')
    category = db.relationship('Category', back_populates='products')
    order_items = db.relationship('OrderItem', back_populates='product')
    reviews = db.relationship('Review', back_populates='product', cascade="all, delete-orphan")
    favorites = db.relationship('Favorite', back_populates='product', cascade="all, delete-orphan")
    reactions = db.relationship('ProductReaction', back_populates='product', cascade="all, delete-orphan")
    comments = db.relationship('ProductComment', back_populates='product', cascade="all, delete-orphan")
    cart_items = db.relationship('CartItem', back_populates='product', cascade="all, delete-orphan")

    @property
    def images(self):
        result = []
        if self.main_image:
            result.append(self.main_image.strip())
        if self.sub_images:
            result.extend([img.strip() for img in self.sub_images.split(',') if img.strip()])
        return ','.join(result) if result else None

    @images.setter
    def images(self, value):
        if not value:
            self.main_image = None
            self.sub_images = None
            return
        parts = [p.strip() for p in value.split(',') if p.strip()]
        if parts:
            self.main_image = parts[0]
            self.sub_images = ','.join(parts[1:]) if len(parts) > 1 else None
        else:
            self.main_image = None
            self.sub_images = None

    def __repr__(self):
        return f'<Product {self.name}>'

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False, index=True)
    delivery_person_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    status = db.Column(db.String(20), default='new', index=True)
    total = db.Column(db.Float, nullable=False)
    delivery_fee = db.Column(db.Float, default=0.0)
    delivery_code = db.Column(db.String(6), nullable=True)
    delivery_address = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_cancelled = db.Column(db.Boolean, default=False)
    payment_method = db.Column(db.String(30), default='cash')
    created_at = db.Column(db.DateTime, default=current_time, index=True)
    delivered_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint('total >= 0', name='ck_order_total_non_negative'),
        CheckConstraint('delivery_fee >= 0', name='ck_order_delivery_fee_non_negative'),
        CheckConstraint(
            "status IN ('new', 'confirmed', 'preparing', 'ready', 'delivering', 'delivered', 'cancelled')",
            name='ck_order_status_valid'
        ),
        CheckConstraint(
            "payment_method IN ('cash', 'wallet', 'bank_transfer', 'manual_delivery')",
            name='ck_order_payment_method_valid'
        ),
        db.Index('ix_order_store_created', 'store_id', 'created_at'),
        db.Index('ix_order_customer_created', 'customer_id', 'created_at'),
        db.Index('ix_order_delivery_created', 'delivery_person_id', 'created_at'),
        db.Index('ix_order_store_status', 'store_id', 'status'),
        db.Index('ix_order_customer_status', 'customer_id', 'status'),
    )

    customer = db.relationship('User', back_populates='orders', foreign_keys=[customer_id])
    store = db.relationship('Store', back_populates='orders')
    delivery_person = db.relationship('User', back_populates='delivery_orders', foreign_keys=[delivery_person_id])
    items = db.relationship('OrderItem', back_populates='order', cascade="all, delete-orphan")
    payments = db.relationship('Payment', back_populates='order', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Order {self.id}>'

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False)
    options_selected = db.Column(db.Text, nullable=True)

    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_orderitem_quantity_positive'),
        CheckConstraint('price >= 0', name='ck_orderitem_price_non_negative'),
    )

    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')

    def __repr__(self):
        return f'<OrderItem {self.product_id} x{self.quantity}>'

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', name='uq_user_product_cart'),
        CheckConstraint('quantity > 0', name='ck_cartitem_quantity_positive'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=current_time)

    user = db.relationship('User', back_populates='cart_items')
    product = db.relationship('Product', back_populates='cart_items')
    store = db.relationship('Store', back_populates='cart_items')

    def to_dict(self):
        return {
            'product_id': self.product_id,
            'quantity': self.quantity,
            'store_id': self.store_id
        }

class Review(db.Model):
    __tablename__ = 'reviews'
    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', name='uq_user_product_review'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating_range')
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=current_time)

    user = db.relationship('User', back_populates='reviews')
    product = db.relationship('Product', back_populates='reviews')

class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', name='uq_user_product_favorite'),
        UniqueConstraint('user_id', 'store_id', name='uq_user_store_favorite'),
        CheckConstraint(
            '(product_id IS NOT NULL AND store_id IS NULL) OR (product_id IS NULL AND store_id IS NOT NULL)',
            name='ck_favorite_one_target'
        ),
        CheckConstraint(
            'product_id IS NOT NULL OR store_id IS NOT NULL',
            name='ck_favorite_at_least_one'
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=current_time)

    user = db.relationship('User', back_populates='favorites')
    product = db.relationship('Product', back_populates='favorites')
    store = db.relationship('Store')

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=True)
    message = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    type = db.Column(db.String(50), default='info', index=True)
    priority = db.Column(db.String(20), default='normal')
    icon = db.Column(db.String(50), nullable=True)
    is_global = db.Column(db.Boolean, default=False)
    extra_data = db.Column(db.Text, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)        # new
    expires_at = db.Column(db.DateTime, nullable=True)     # new
    created_at = db.Column(db.DateTime, default=current_time)

    __table_args__ = (
        db.Index('ix_notification_user_read', 'user_id', 'is_read'),
        db.Index('ix_notification_user_type', 'user_id', 'type'),
        db.Index('ix_notification_expires', 'expires_at'),
    )

    user = db.relationship('User', back_populates='notifications')

class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.String(200), nullable=False)
    auth = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=current_time)

    user = db.relationship('User', back_populates='push_subscriptions')

    def to_dict(self):
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh,
                'auth': self.auth
            }
        }

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True, index=True)
    start_date = db.Column(db.DateTime, default=current_time)
    end_date = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)
    payment_ref = db.Column(db.String(100), nullable=True)
    proof_image = db.Column(db.String(300), nullable=True)
    payment_method = db.Column(db.String(30), default='manual_delivery')
    confirmation_code = db.Column(db.String(20), nullable=True)
    expiry_notified = db.Column(db.Boolean, default=False)

    __table_args__ = (
        CheckConstraint('amount >= 0', name='ck_subscription_amount_non_negative'),
        CheckConstraint("status IN ('pending', 'paid', 'cancelled', 'expired')", name='ck_subscription_status_valid'),
        CheckConstraint('(user_id IS NOT NULL) OR (store_id IS NOT NULL)', name='ck_subscription_user_or_store'),
        CheckConstraint(
            "payment_method IN ('cash', 'wallet', 'bank_transfer', 'manual_delivery')",
            name='ck_subscription_payment_method_valid'
        ),
        db.Index('ix_subscription_store_status', 'store_id', 'status'),
        db.Index('ix_subscription_end_date', 'end_date'),
    )

    user = db.relationship('User', back_populates='subscriptions', foreign_keys=[user_id])
    store = db.relationship('Store', back_populates='subscriptions', foreign_keys=[store_id])
    payments = db.relationship('Payment', back_populates='subscription')

class ProductReaction(db.Model):
    __tablename__ = 'product_reactions'
    __table_args__ = (
        UniqueConstraint('product_id', 'user_id', name='uq_product_user_reaction'),
        CheckConstraint("reaction_type IN ('like', 'love', 'wow', 'sad', 'angry')", name='ck_reaction_type_valid')
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    reaction_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=current_time)

    product = db.relationship('Product', back_populates='reactions')
    user = db.relationship('User')

class ProductComment(db.Model):
    __tablename__ = 'product_comments'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=current_time)

    product = db.relationship('Product', back_populates='comments')
    user = db.relationship('User', back_populates='product_comments')

class PasswordReset(db.Model):
    __tablename__ = 'password_resets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=current_time, index=True)

    __table_args__ = (
        CheckConstraint('sender_id != receiver_id', name='ck_chat_no_self_message'),
    )

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.String(200), nullable=False)
    updated_at = db.Column(db.DateTime, default=current_time, onupdate=current_time)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=True, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True, index=True)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(30), nullable=False, default='cash')
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    reference = db.Column(db.String(100), nullable=True)
    proof_image = db.Column(db.String(300), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=current_time, index=True)
    updated_at = db.Column(db.DateTime, default=current_time, onupdate=current_time)

    __table_args__ = (
        CheckConstraint('amount >= 0', name='ck_payment_amount_non_negative'),
        CheckConstraint("status IN ('pending', 'paid', 'failed', 'refunded')", name='ck_payment_status_valid'),
        CheckConstraint(
            "method IN ('cash', 'wallet', 'bank_transfer', 'manual_delivery')",
            name='ck_payment_method_valid'
        ),
        CheckConstraint(
            '(order_id IS NOT NULL) OR (store_id IS NOT NULL) OR (subscription_id IS NOT NULL)',
            name='ck_payment_has_reference'
        ),
    )

    user = db.relationship('User', back_populates='payments')
    order = db.relationship('Order', back_populates='payments')
    store = db.relationship('Store', back_populates='payments')
    subscription = db.relationship('Subscription', back_populates='payments')

    def __repr__(self):
        return f'<Payment {self.id} - {self.amount}>'

class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    attempted_at = db.Column(db.DateTime, default=current_time, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)

    __table_args__ = (
        db.Index('ix_login_attempt_ip_time', 'ip_address', 'attempted_at'),
    )

    user = db.relationship('User', foreign_keys=[user_id])

class PasswordResetAttempt(db.Model):
    __tablename__ = 'password_reset_attempts'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=True, index=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    attempted_at = db.Column(db.DateTime, default=current_time, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)

    __table_args__ = (
        db.Index('ix_reset_email_time', 'email', 'attempted_at'),
        db.Index('ix_reset_ip_time', 'ip_address', 'attempted_at'),
    )

    user = db.relationship('User', foreign_keys=[user_id])
