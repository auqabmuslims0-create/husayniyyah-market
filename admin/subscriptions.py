from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
import models
from services.subscription_service import SubscriptionService
from decorators import role_required
from . import admin_bp

@admin_bp.route('/admin/subscriptions')
@role_required('admin')
def admin_subscriptions():
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = models.Subscription.query.filter(models.Subscription.store_id.isnot(None)).options(
        selectinload(models.Subscription.user),
        selectinload(models.Subscription.store)
    )

    if q:
        query = query.filter(
            or_(
                models.Subscription.payment_ref.ilike(f'%{q}%'),
                models.Subscription.store.has(models.Store.name.ilike(f'%{q}%')),
                models.Subscription.user.has(models.User.username.ilike(f'%{q}%'))
            )
        )
    if status_filter in ['pending', 'paid', 'cancelled', 'expired']:
        query = query.filter(models.Subscription.status == status_filter)

    pagination = query.order_by(models.Subscription.start_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    subs = pagination.items
    sub_ids = [sub.id for sub in subs]
    payments_map = {}
    if sub_ids:
        all_payments = models.Payment.query.filter(models.Payment.subscription_id.in_(sub_ids)).all()
        for pay in all_payments:
            payments_map.setdefault(pay.subscription_id, []).append(pay)
    return render_template('admin/admin_subscriptions.html', subs=subs, pagination=pagination,
                           q=q, status_filter=status_filter, payments_map=payments_map)

@admin_bp.route('/admin/subscriptions/<int:sub_id>/approve', methods=['POST'])
@role_required('admin')
def admin_approve_subscription(sub_id):
    success, msg = SubscriptionService.approve_subscription(sub_id)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('admin.admin_subscriptions'))

@admin_bp.route('/admin/subscriptions/<int:sub_id>/reject', methods=['POST'])
@role_required('admin')
def admin_reject_subscription(sub_id):
    success, msg = SubscriptionService.reject_subscription(sub_id)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('admin.admin_subscriptions'))
