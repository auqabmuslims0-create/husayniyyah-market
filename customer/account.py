from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort, jsonify
from sqlalchemy.orm import joinedload
from database import db
import models
from time_utils import current_time
from utils import safe_redirect_target, safe_referrer
from decorators import login_required
from services.notification_service import NotificationService

account_bp = Blueprint('account', __name__)

@account_bp.route('/api/favorites/sync', methods=['POST'])
@login_required
def sync_favorites():
    data = request.get_json(silent=True) or {}
    favs = data.get('favorites', {})
    user_id = session['user_id']
    products = favs.get('products', [])
    stores = favs.get('stores', [])

    models.Favorite.query.filter_by(user_id=user_id).delete()
    for pid in products:
        try:
            pid_int = int(pid)
            if models.Product.query.get(pid_int):
                db.session.add(models.Favorite(user_id=user_id, product_id=pid_int))
        except (ValueError, TypeError):
            continue
    for sid in stores:
        try:
            sid_int = int(sid)
            if models.Store.query.get(sid_int):
                db.session.add(models.Favorite(user_id=user_id, store_id=sid_int))
        except (ValueError, TypeError):
            continue
    db.session.commit()
    return jsonify({'status': 'success'})

@account_bp.route('/favorites')
@login_required
def favorites():
    user_id = session['user_id']
    favs = models.Favorite.query.filter_by(user_id=user_id).options(
        joinedload(models.Favorite.product),
        joinedload(models.Favorite.store)
    ).all()
    return render_template('customer/favorites.html', favs=favs)

# ========== إزالة مسارات الإشعارات نهائيًا من هنا ==========
# تم نقلها إلى notifications/routes.py

@account_bp.route('/favorite/toggle/product/<int:product_id>', methods=['POST'])
@login_required
def toggle_favorite_product(product_id):
    user_id = session['user_id']

    existing = models.Favorite.query.filter_by(user_id=user_id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('تمت إزالة المنتج من المفضلة')
    else:
        fav = models.Favorite(user_id=user_id, product_id=product_id)
        db.session.add(fav)
        db.session.commit()
        flash('تمت إضافة المنتج إلى المفضلة')

    next_url = safe_redirect_target(request.form.get('next')) or safe_referrer() or url_for('market.market')
    return redirect(next_url)

@account_bp.route('/favorite/toggle/store/<int:store_id>', methods=['POST'])
@login_required
def toggle_favorite_store(store_id):
    user_id = session['user_id']

    existing = models.Favorite.query.filter_by(user_id=user_id, store_id=store_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('تمت إزالة المتجر من المفضلة')
    else:
        fav = models.Favorite(user_id=user_id, store_id=store_id)
        db.session.add(fav)
        db.session.commit()
        flash('تمت إضافة المتجر إلى المفضلة')

    next_url = safe_redirect_target(request.form.get('next')) or safe_referrer() or url_for('stores.stores_page')
    return redirect(next_url)

@account_bp.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    user_id = session['user_id']
    product = models.Product.query.get_or_404(product_id)

    rating_str = request.form.get('rating', '').strip()
    comment = request.form.get('comment', '').strip()

    try:
        rating = int(rating_str)
    except (TypeError, ValueError):
        rating = 0

    if rating < 1 or rating > 5:
        flash('التقييم يجب أن يكون بين 1 و 5', 'error')
        return redirect(url_for('stores.product_public', product_id=product.id))

    if not comment:
        flash('يرجى كتابة تعليق', 'error')
        return redirect(url_for('stores.product_public', product_id=product.id))

    existing = models.Review.query.filter_by(user_id=user_id, product_id=product.id).first()
    if existing:
        existing.rating = rating
        existing.comment = comment
    else:
        review = models.Review(
            user_id=user_id,
            product_id=product.id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)

    db.session.commit()
    flash('تم حفظ تقييمك', 'success')
    return redirect(url_for('stores.product_public', product_id=product.id))
