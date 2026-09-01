from flask import render_template
from sqlalchemy import func
from database import db
import models
from decorators import role_required
from . import admin_bp

@admin_bp.route('/admin/finance')
@role_required('admin')
def admin_finance():
    subscription_revenue = db.session.query(func.sum(models.Subscription.amount)).filter(
        models.Subscription.status == 'paid'
    ).scalar() or 0

    paid_subscriptions = models.Subscription.query.filter_by(status='paid').count()

    order_revenue = db.session.query(func.sum(models.Order.total)).filter(
        models.Order.status != 'cancelled'
    ).scalar() or 0

    total_orders = models.Order.query.filter(models.Order.status != 'cancelled').count()

    delivery_fee_revenue = db.session.query(func.sum(models.Order.delivery_fee)).filter(
        models.Order.status != 'cancelled'
    ).scalar() or 0

    delivered_orders_count = models.Order.query.filter(models.Order.delivery_person_id.isnot(None)).count()

    total_users = models.User.query.count()
    total_stores = models.Store.query.count()
    active_stores = models.Store.query.filter_by(subscription_status='active').count()
    pending_subscriptions = models.Subscription.query.filter_by(status='pending').count()

    # استعلام مجمع لأدوار المستخدمين
    user_role_counts = db.session.query(
        models.User.role, func.count(models.User.id).label('count')
    ).group_by(models.User.role).all()

    # استعلام مجمع لحالات الطلبات
    order_status_counts = db.session.query(
        models.Order.status, func.count(models.Order.id).label('count')
    ).group_by(models.Order.status).all()

    total_payments = db.session.query(func.sum(models.Payment.amount)).filter(models.Payment.status == 'paid').scalar() or 0

    return render_template(
        'admin/admin_finance.html',
        subscription_revenue=subscription_revenue,
        paid_subscriptions=paid_subscriptions,
        order_revenue=order_revenue,
        total_orders=total_orders,
        total_users=total_users,
        total_stores=total_stores,
        active_stores=active_stores,
        pending_subscriptions=pending_subscriptions,
        user_role_counts=user_role_counts,
        order_status_counts=order_status_counts,
        delivery_fee_revenue=delivery_fee_revenue,
        delivered_orders_count=delivered_orders_count,
        total_payments=total_payments
    )
