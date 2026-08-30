from flask import Blueprint, render_template, request
from sqlalchemy.orm import joinedload
import models

offers_bp = Blueprint('offers', __name__)

@offers_bp.route('/offers')
def offers_page():
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)
    store_id = request.args.get('store_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = models.Product.query.join(models.Store).filter(
        models.Product.is_offer == True,
        models.Store.subscription_status == 'active'
    ).options(
        joinedload(models.Product.store),
        joinedload(models.Product.category)
    ).order_by(models.Product.created_at.desc())

    if q:
        query = query.filter(models.Product.name.ilike(f'%{q}%'))
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    if store_id:
        query = query.filter(models.Product.store_id == store_id)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    categories = models.Category.query.join(models.Product).filter(
        models.Product.is_offer == True,
        models.Product.store.has(models.Store.subscription_status == 'active')
    ).distinct().all()

    stores = models.Store.query.join(models.Product).filter(
        models.Product.is_offer == True,
        models.Store.subscription_status == 'active'
    ).distinct().all()

    return render_template('customer/offers.html',
                           products=pagination.items,
                           pagination=pagination,
                           q=q,
                           selected_category=category_id,
                           selected_store=store_id,
                           categories=categories,
                           stores=stores)
