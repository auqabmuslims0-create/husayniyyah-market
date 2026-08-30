from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort, jsonify
from database import db
import models
from sqlalchemy.orm import joinedload
from time_utils import current_time
from datetime import timedelta
from services.order_service import OrderService
from decorators import role_required

delivery_bp = Blueprint('delivery', __name__)

@delivery_bp.route('/delivery')
@role_required('delivery')
def delivery_dashboard():
    user = db.session.get(models.User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))

    status_filter = request.args.get('status', '').strip()
    allowed_statuses = ['ready', 'delivering', 'delivered']

    try:
        query = models.Order.query.filter_by(delivery_person_id=user.id).options(
            joinedload(models.Order.store),
            joinedload(models.Order.customer),
            joinedload(models.Order.items).joinedload(models.OrderItem.product)
        )

        if status_filter in allowed_statuses:
            query = query.filter(models.Order.status == status_filter)

        all_orders = query.order_by(models.Order.created_at.desc()).limit(50).all()

        ready_orders = [o for o in all_orders if o.status == 'ready']
        delivering_orders = [o for o in all_orders if o.status == 'delivering']
        delivered_orders = [o for o in all_orders if o.status == 'delivered']

        now = current_time()
        map_orders = []
        for order in all_orders:
            if order.latitude and order.longitude:
                if order.status == 'delivered':
                    delivered_time = order.delivered_at or order.created_at
                    if now - delivered_time > timedelta(hours=12):
                        continue
                map_orders.append(order)

        active_orders_count = models.Order.query.filter(
            models.Order.delivery_person_id == user.id,
            models.Order.status.in_(['ready', 'delivering'])
        ).count()

        shift_info = None
        if user.shift_start_time and user.shift_end_time:
            shift_info = {
                'start': user.shift_start_time.strftime('%H:%M'),
                'end': user.shift_end_time.strftime('%H:%M')
            }

        notifications = models.Notification.query.filter_by(user_id=user.id).order_by(
            models.Notification.created_at.desc()
        ).limit(5).all()

        stores_on_map = models.Store.query.filter(
            models.Store.latitude.isnot(None),
            models.Store.longitude.isnot(None)
        ).all()

    except Exception as e:
        app.logger.exception('خطأ في تحميل لوحة المندوب')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('auth.dashboard'))

    return render_template(
        'delivery/delivery_dashboard.html',
        user=user,
        orders=all_orders,
        ready_orders=ready_orders,
        delivering_orders=delivering_orders,
        delivered_orders=delivered_orders,
        status_filter=status_filter,
        allowed_statuses=allowed_statuses,
        notifications=notifications,
        map_orders=map_orders,
        shift_info=shift_info,
        active_orders_count=active_orders_count,
        stores_on_map=stores_on_map
    )

@delivery_bp.route('/delivery/orders/<int:order_id>/start', methods=['POST'])
@role_required('delivery')
def delivery_order_start(order_id):
    user = db.session.get(models.User, session['user_id'])
    if not user:
        return redirect(url_for('auth.login'))

    order = models.Order.query.get_or_404(order_id)

    try:
        OrderService.start_delivery(user, order)
        flash('تم بدء التسليم', 'success')
    except PermissionError as e:
        abort(403, description=str(e))
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        app.logger.exception('خطأ في بدء التسليم')
        flash('حدث خطأ أثناء بدء التسليم', 'error')

    return redirect(url_for('delivery.delivery_dashboard'))

@delivery_bp.route('/delivery/orders/<int:order_id>/deliver', methods=['POST'])
@role_required('delivery')
def delivery_order_deliver(order_id):
    user = db.session.get(models.User, session['user_id'])
    if not user:
        return redirect(url_for('auth.login'))

    order = models.Order.query.get_or_404(order_id)
    delivery_code = request.form.get('delivery_code', '').strip()

    try:
        OrderService.complete_delivery(user, order, delivery_code)
        flash('تم تأكيد التسليم', 'success')
    except PermissionError as e:
        abort(403, description=str(e))
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        db.session.rollback()
        app.logger.exception('خطأ في تأكيد التسليم')
        flash('حدث خطأ أثناء تأكيد التسليم', 'error')

    return redirect(url_for('delivery.delivery_dashboard'))

@delivery_bp.route('/api/delivery_notifications')
@role_required('delivery')
def api_delivery_notifications():
    user_id = session['user_id']
    notifs = models.Notification.query.filter_by(user_id=user_id, is_read=False).order_by(
        models.Notification.created_at.desc()
    ).limit(5).all()
    data = [{'title': n.title, 'message': n.message} for n in notifs]
    return jsonify({'status': 'success', 'notifications': data})

@delivery_bp.route('/delivery/availability', methods=['POST'])
@role_required('delivery')
def update_availability():
    user = db.session.get(models.User, session['user_id'])
    if not user:
        return redirect(url_for('auth.login'))

    is_available = request.form.get('is_available', 'false') == 'true'
    user.is_available = is_available
    db.session.commit()

    flash(f'تم تحديث حالتك إلى {"متاح" if is_available else "غير متاح"}', 'success')
    return redirect(url_for('delivery.delivery_dashboard'))
