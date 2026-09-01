from flask import request, jsonify, session
from database import db
import models
from shared.decorators import login_required
from shared.services.push_service import get_or_create_vapid_keys
from . import api_bp

@api_bp.route('/push/vapid_public_key', methods=['GET'])
def push_vapid_public_key():
    public_key, _ = get_or_create_vapid_keys()
    return jsonify({'public_key': public_key})

@api_bp.route('/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    subscription = data.get('subscription')
    if not subscription:
        return jsonify({'message': 'بيانات الاشتراك مطلوبة'}), 400

    endpoint = subscription.get('endpoint')
    keys = subscription.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not endpoint or not p256dh or not auth:
        return jsonify({'message': 'بيانات الاشتراك غير مكتملة'}), 400

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'يجب تسجيل الدخول'}), 401

    # التحقق من عدم وجود اشتراك مطابق
    existing = models.PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        if existing.user_id != user_id:
            # إذا كان الاشتراك لمسخدم آخر، نحدّثه للمستخدم الحالي
            existing.user_id = user_id
            existing.p256dh = p256dh
            existing.auth = auth
            try:
                db.session.commit()
                return jsonify({'message': 'تم تحديث الاشتراك'}), 200
            except Exception:
                db.session.rollback()
                return jsonify({'message': 'حدث خطأ أثناء التحديث'}), 500
        return jsonify({'message': 'الاشتراك موجود بالفعل'}), 200

    new_sub = models.PushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth
    )
    db.session.add(new_sub)
    try:
        db.session.commit()
        return jsonify({'message': 'تم الاشتراك في الإشعارات'}), 201
    except Exception:
        db.session.rollback()
        return jsonify({'message': 'حدث خطأ أثناء الحفظ'}), 500

@api_bp.route('/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint')
    if not endpoint:
        return jsonify({'message': 'endpoint مطلوب'}), 400

    user_id = session.get('user_id')
    sub = models.PushSubscription.query.filter_by(endpoint=endpoint, user_id=user_id).first()
    if sub:
        db.session.delete(sub)
        try:
            db.session.commit()
            return jsonify({'message': 'تم إلغاء الاشتراك'}), 200
        except Exception:
            db.session.rollback()
            return jsonify({'message': 'حدث خطأ أثناء الإلغاء'}), 500
    return jsonify({'message': 'لا يوجد اشتراك مطابق'}), 404
