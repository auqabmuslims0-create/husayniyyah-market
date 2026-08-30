from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from database import db
import models
from decorators import login_required

services_bp = Blueprint('services', __name__)

def _is_ajax():
    """التحقق الصارم من طلبات AJAX."""
    # أولاً: وجود X-Requested-With يعتبر AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    # ثانياً: قبول JSON صريح بدون */*
    accept = request.headers.get('Accept', '')
    if 'application/json' in accept and '*/*' not in accept:
        return True
    # أي شيء آخر يعتبر طلب عادي
    return False

@services_bp.route('/services')
def services_page():
    return render_template('customer/services.html')

@services_bp.route('/support')
@login_required
def support():
    return render_template('customer/contact.html')

@services_bp.route('/contact')
@login_required
def contact():
    return redirect(url_for('services.support'))

@services_bp.route('/contact/send', methods=['POST'])
@login_required
def send_contact_message():
    if 'user_id' not in session:
        if _is_ajax():
            return jsonify({'status': 'error', 'message': 'يجب تسجيل الدخول'}), 401
        flash('يجب تسجيل الدخول أولاً', 'error')
        return redirect(url_for('auth.login'))

    user = db.session.get(models.User, session['user_id'])
    if not user:
        if _is_ajax():
            return jsonify({'status': 'error', 'message': 'جلسة غير صالحة'}), 401
        session.clear()
        flash('الجلسة غير صالحة، يرجى تسجيل الدخول', 'error')
        return redirect(url_for('auth.login'))

    message = request.form.get('message', '').strip()
    if not message:
        if _is_ajax():
            return jsonify({'status': 'error', 'message': 'الرسالة فارغة'}), 400
        flash('يرجى كتابة رسالة', 'error')
        return redirect(url_for('services.support'))

    admin = models.User.query.filter_by(role='admin', is_active=True).first()
    if not admin:
        if _is_ajax():
            return jsonify({'status': 'error', 'message': 'لا يوجد دعم متاح حالياً'}), 404
        flash('لا يوجد دعم متاح حالياً', 'error')
        return redirect(url_for('services.support'))

    try:
        msg = models.ChatMessage(
            sender_id=user.id,
            receiver_id=admin.id,
            message=message,
            is_read=False
        )
        db.session.add(msg)
        db.session.commit()
        # إذا كان الطلب AJAX حقًا (X-Requested-With) نرجع JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success'})
        # وإلا نعيد توجيه عادي
        flash('تم إرسال رسالتك بنجاح', 'success')
        return redirect(url_for('services.support'))
    except Exception:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'حدث خطأ أثناء الإرسال'}), 500
        flash('حدث خطأ أثناء الإرسال، حاول مرة أخرى', 'error')
        return redirect(url_for('services.support'))

@services_bp.route('/contact/messages')
@login_required
def fetch_contact_messages():
    if 'user_id' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'messages': []}), 401
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    admin = models.User.query.filter_by(role='admin', is_active=True).first()
    if not admin:
        return jsonify({'status': 'success', 'messages': []})

    try:
        messages = models.ChatMessage.query.filter(
            ((models.ChatMessage.sender_id == user_id) & (models.ChatMessage.receiver_id == admin.id)) |
            ((models.ChatMessage.sender_id == admin.id) & (models.ChatMessage.receiver_id == user_id))
        ).order_by(models.ChatMessage.created_at.asc()).all()

        data = []
        for msg in messages:
            data.append({
                'id': msg.id,
                'message': msg.message,
                'is_mine': msg.sender_id == user_id,
                'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M') if msg.created_at else ''
            })
        return jsonify({'status': 'success', 'messages': data})
    except Exception:
        return jsonify({'status': 'error', 'messages': []}), 500
