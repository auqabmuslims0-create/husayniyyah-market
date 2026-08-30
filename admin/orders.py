from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from database import db
import models
from services.order_service import OrderService
from services.notification_service import NotificationService
from decorators import role_required
from time_utils import current_time
from . import admin_bp

@admin_bp.route('/admin/orders')
@role_required('admin')
def admin_orders():
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = models.Order.query.options(
        selectinload(models.Order.customer),
        selectinload(models.Order.store),
        selectinload(models.Order.items).selectinload(models.OrderItem.product),
        selectinload(models.Order.delivery_person)
    )

    if q:
        if q.isdigit():
            query = query.filter(models.Order.id == int(q))
        else:
            query = query.filter(
                or_(
                    models.Order.customer.has(models.User.username.ilike(f'%{q}%')),
                    models.Order.store.has(models.Store.name.ilike(f'%{q}%'))
                )
            )

    allowed_statuses = ['new', 'confirmed', 'preparing', 'ready', 'delivering', 'delivered', 'cancelled']
    if status_filter in allowed_statuses:
        query = query.filter(models.Order.status == status_filter)

    pagination = query.order_by(models.Order.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    orders = pagination.items

    grouped = {}
    for order in orders:
        store_id = order.store_id
        if store_id not in grouped:
            grouped[store_id] = {
                'store': order.store,
                'orders': [],
                'total_count': 0,
                'total_amount': 0.0
            }
        grouped[store_id]['orders'].append(order)
        grouped[store_id]['total_count'] += 1
        grouped[store_id]['total_amount'] += order.total

    grouped_list = list(grouped.values())
    grouped_list.sort(key=lambda g: g['store'].name if g['store'] else '')

    return render_template('admin/admin_orders.html', grouped_orders=grouped_list,
                           pagination=pagination, q=q, status_filter=status_filter,
                           allowed_statuses=allowed_statuses)

@admin_bp.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@role_required('admin')
def admin_update_order_status(order_id):
    order = models.Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    allowed_statuses = ['new', 'confirmed', 'preparing', 'ready', 'delivering', 'delivered', 'cancelled']
    if new_status not in allowed_statuses:
        flash('حالة غير صالحة', 'error')
        return redirect(url_for('admin.admin_orders'))

    if new_status == 'cancelled' and order.status != 'cancelled':
        for item in order.items:
            product = item.product
            if product:
                product.stock_quantity += item.quantity
                db.session.add(product)

    order.status = new_status
    if new_status == 'cancelled':
        order.is_cancelled = True
    elif new_status == 'delivered':
        order.delivered_at = current_time()

    try:
        db.session.commit()

        # إرسال إشعارات
        if order.customer_id:
            NotificationService.send_to_user(
                user_id=order.customer_id,
                message=f'تم تحديث حالة طلبك رقم {order.id} إلى {new_status}',
                link=url_for('cart.cart'),
                type_=NotificationService.TYPE_ORDER
            )
        if order.store_id:
            store = db.session.get(models.Store, order.store_id)
            if store and store.owner_id:
                NotificationService.send_to_user(
                    user_id=store.owner_id,
                    message=f'قام المدير بتحديث حالة الطلب رقم {order.id} إلى {new_status}',
                    link=url_for('store.store_orders', store_id=store.id),
                    type_=NotificationService.TYPE_ORDER
                )
        db.session.commit()
        flash('تم تحديث حالة الطلب بنجاح', 'success')
    except Exception:
        db.session.rollback()
        flash('حدث خطأ أثناء تحديث حالة الطلب', 'error')
    return redirect(url_for('admin.admin_orders'))
