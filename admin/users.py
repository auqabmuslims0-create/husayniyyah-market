from flask import render_template, request, redirect, url_for, session, flash, abort
from sqlalchemy import func, or_
from database import db
import models
from services.user_service import UserService
from decorators import role_required
from . import admin_bp

@admin_bp.route('/admin/users')
@role_required('admin')
def admin_users():
    role_filter = request.args.get('role', '').strip()
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    temp_password = session.pop('reset_password_temp', None)

    query = models.User.query

    if role_filter in ['admin', 'owner', 'customer', 'delivery']:
        query = query.filter_by(role=role_filter)
    if q:
        query = query.filter(
            or_(
                models.User.username.ilike(f'%{q}%'),
                models.User.email.ilike(f'%{q}%'),
                models.User.phone.ilike(f'%{q}%')
            )
        )

    pagination = query.order_by(models.User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items

    user_stats = {}
    if users:
        user_ids = [u.id for u in users]
        # استخدام استعلامات مجمعة مرة واحدة لكل إحصائية
        customer_counts = dict(db.session.query(
            models.Order.customer_id, func.count(models.Order.id)
        ).filter(models.Order.customer_id.in_(user_ids)).group_by(models.Order.customer_id).all())

        store_counts = dict(db.session.query(
            models.Store.owner_id, func.count(models.Store.id)
        ).filter(models.Store.owner_id.in_(user_ids)).group_by(models.Store.owner_id).all())

        delivery_counts = dict(db.session.query(
            models.Order.delivery_person_id, func.count(models.Order.id)
        ).filter(models.Order.delivery_person_id.in_(user_ids)).group_by(models.Order.delivery_person_id).all())

        favorite_counts = dict(db.session.query(
            models.Favorite.user_id, func.count(models.Favorite.id)
        ).filter(models.Favorite.user_id.in_(user_ids)).group_by(models.Favorite.user_id).all())

        review_counts = dict(db.session.query(
            models.Review.user_id, func.count(models.Review.id)
        ).filter(models.Review.user_id.in_(user_ids)).group_by(models.Review.user_id).all())

        comment_counts = dict(db.session.query(
            models.ProductComment.user_id, func.count(models.ProductComment.id)
        ).filter(models.ProductComment.user_id.in_(user_ids)).group_by(models.ProductComment.user_id).all())

        for u in users:
            user_stats[u.id] = {
                'orders_count': customer_counts.get(u.id, 0),
                'stores_count': store_counts.get(u.id, 0),
                'delivery_count': delivery_counts.get(u.id, 0),
                'favorites_count': favorite_counts.get(u.id, 0),
                'reviews_count': review_counts.get(u.id, 0),
                'comments_count': comment_counts.get(u.id, 0),
            }

    return render_template('admin/admin_users.html',
                           users=users,
                           pagination=pagination,
                           role_filter=role_filter,
                           q=q,
                           temp_password=temp_password,
                           user_stats=user_stats)

@admin_bp.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@role_required('admin')
def admin_toggle_user(user_id):
    admin_user = db.session.get(models.User, session['user_id'])
    success, msg, _ = UserService.toggle_user_status(user_id, admin_user_id=admin_user.id)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/admin/users/<int:user_id>/reset_password', methods=['POST'])
@role_required('admin')
def admin_reset_password(user_id):
    success, msg, temp_password = UserService.reset_password(user_id)
    if success:
        session['reset_password_temp'] = temp_password
        flash(f'{msg}. كلمة المرور المؤقتة: {temp_password}', 'success')
    else:
        flash(msg, 'error')
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def admin_delete_user(user_id):
    admin_user = db.session.get(models.User, session['user_id'])
    success, msg = UserService.delete_user_fully(user_id, admin_user_id=admin_user.id)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/admin/users/<int:user_id>/contact', methods=['GET', 'POST'])
@role_required('admin')
def admin_contact_user(user_id):
    target_user = models.User.query.get_or_404(user_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        if not title or not message:
            flash('العنوان والموضوع مطلوبان', 'error')
            return redirect(url_for('admin.admin_contact_user', user_id=target_user.id))

        from services.notification_service import NotificationService
        NotificationService.send_to_user(
            user_id=target_user.id,
            title=title,
            message=message,
            link=None,
            type_=NotificationService.TYPE_MESSAGE
        )
        db.session.commit()
        flash('تم إرسال الرسالة بنجاح', 'success')
        return redirect(url_for('admin.admin_users'))

    return render_template('admin/admin_contact_user.html', target_user=target_user)
