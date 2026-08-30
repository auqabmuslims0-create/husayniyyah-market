from flask import request, jsonify
from database import db
import models
from services.order_service import OrderService
from . import api_bp
from .helpers import token_required, serialize_order

@api_bp.route('/delivery/orders', methods=['GET'])
@token_required
def delivery_get_orders(current_user):
    if current_user.role != 'delivery':
        return jsonify({'message': 'غير مسموح'}), 403
    status = request.args.get('status')
    query = models.Order.query.filter_by(delivery_person_id=current_user.id)
    if status:
        query = query.filter_by(status=status)
    orders = query.order_by(models.Order.created_at.desc()).all()
    return jsonify({'orders': [serialize_order(o) for o in orders]}), 200

@api_bp.route('/delivery/orders/<int:order_id>/start', methods=['POST'])
@token_required
def delivery_start_order(current_user, order_id):
    if current_user.role != 'delivery':
        return jsonify({'message': 'غير مسموح'}), 403
    order = models.Order.query.get_or_404(order_id)
    try:
        OrderService.start_delivery(current_user, order)
        return jsonify({'message': 'تم بدء التسليم'}), 200
    except PermissionError as e:
        return jsonify({'message': str(e)}), 403
    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'message': 'حدث خطأ'}), 500

@api_bp.route('/delivery/orders/<int:order_id>/deliver', methods=['POST'])
@token_required
def delivery_deliver_order(current_user, order_id):
    if current_user.role != 'delivery':
        return jsonify({'message': 'غير مسموح'}), 403
    order = models.Order.query.get_or_404(order_id)
    data = request.get_json(silent=True) or {}
    code = data.get('delivery_code')
    try:
        OrderService.complete_delivery(current_user, order, code)
        return jsonify({'message': 'تم تأكيد التسليم'}), 200
    except PermissionError as e:
        return jsonify({'message': str(e)}), 403
    except ValueError as e:
        return jsonify({'message': str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'message': 'حدث خطأ'}), 500

@api_bp.route('/delivery/notifications', methods=['GET'])
@token_required
def delivery_notifications(current_user):
    if current_user.role != 'delivery':
        return jsonify({'message': 'غير مسموح'}), 403
    notifs = models.Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(
        models.Notification.created_at.desc()
    ).limit(5).all()
    data = [{'title': n.title, 'message': n.message} for n in notifs]
    return jsonify({'status': 'success', 'notifications': data}), 200
