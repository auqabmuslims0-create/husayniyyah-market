from flask import Blueprint, render_template, session
from sqlalchemy.orm import joinedload
import models

reels_bp = Blueprint('reels', __name__)

@reels_bp.route('/reels')
def reels():
    videos = models.Product.query.join(models.Store).filter(
        models.Product.video.isnot(None),
        models.Store.subscription_status == 'active'
    ).options(joinedload(models.Product.store)).all()

    user_reaction_map = {}
    if 'user_id' in session:
        user_reactions = models.ProductReaction.query.filter_by(user_id=session['user_id']).all()
        for r in user_reactions:
            user_reaction_map[r.product_id] = r.reaction_type

    return render_template('customer/reels.html', videos=videos, user_reaction_map=user_reaction_map)
