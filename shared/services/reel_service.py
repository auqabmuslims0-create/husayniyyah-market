from sqlalchemy.orm import joinedload
from database import db
import models
from shared.time_utils import current_time

class ReelService:
    @staticmethod
    def get_feed(page=1, per_page=10, user_id=None):
        """
        جلب قائمة الريلز النشطة من المتاجر المشتركة (active subscription)
        مع ترتيب زمني تنازلي.
        إذا user_id معطى، نضيف خريطة تفاعلات المستخدم.
        """
        query = models.Reel.query.join(models.Store).filter(
            models.Reel.is_active == True,
            models.Store.subscription_status == 'active'
        ).options(
            joinedload(models.Reel.store),
            joinedload(models.Reel.product),
            joinedload(models.Reel.reactions),
            joinedload(models.Reel.comments).joinedload(models.ReelComment.user)
        ).order_by(models.Reel.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        reels = pagination.items

        user_reaction_map = {}
        if user_id:
            user_reactions = models.ReelReaction.query.filter_by(user_id=user_id).all()
            for r in user_reactions:
                user_reaction_map[r.reel_id] = r.reaction_type

        return reels, pagination, user_reaction_map

    @staticmethod
    def get_reel_by_id(reel_id):
        return models.Reel.query.options(
            joinedload(models.Reel.store),
            joinedload(models.Reel.product),
            joinedload(models.Reel.reactions),
            joinedload(models.Reel.comments).joinedload(models.ReelComment.user)
        ).get(reel_id)

    @staticmethod
    def increment_view(reel_id):
        reel = models.Reel.query.get(reel_id)
        if reel:
            reel.views += 1
            db.session.commit()

    @staticmethod
    def toggle_reaction(reel_id, user_id, reaction_type):
        reel = models.Reel.query.get_or_404(reel_id)
        existing = models.ReelReaction.query.filter_by(reel_id=reel_id, user_id=user_id).first()
        if existing:
            if existing.reaction_type == reaction_type:
                db.session.delete(existing)
                db.session.commit()
                return {'removed': True}
            else:
                existing.reaction_type = reaction_type
                db.session.commit()
                return {'updated': True}
        else:
            reaction = models.ReelReaction(reel_id=reel_id, user_id=user_id, reaction_type=reaction_type)
            db.session.add(reaction)
            db.session.commit()
            return {'added': True}

    @staticmethod
    def add_comment(reel_id, user_id, text):
        reel = models.Reel.query.get_or_404(reel_id)
        comment = models.ReelComment(reel_id=reel_id, user_id=user_id, text=text)
        db.session.add(comment)
        db.session.commit()
        return comment

    @staticmethod
    def update_comment(comment_id, user_id, new_text):
        comment = models.ReelComment.query.get_or_404(comment_id)
        if comment.user_id != user_id:
            return None
        comment.text = new_text
        db.session.commit()
        return comment

    @staticmethod
    def delete_comment(comment_id, user_id):
        comment = models.ReelComment.query.get_or_404(comment_id)
        if comment.user_id != user_id:
            return False
        db.session.delete(comment)
        db.session.commit()
        return True

    @staticmethod
    def serialize_reel(reel, user_reaction_map=None):
        data = {
            'id': reel.id,
            'video_url': reel.video_url,
            'thumbnail_url': reel.thumbnail_url,
            'caption': reel.caption,
            'views': reel.views,
            'created_at': reel.created_at.strftime('%Y-%m-%d %H:%M') if reel.created_at else None,
            'store': {
                'id': reel.store.id,
                'name': reel.store.name,
                'logo_url': reel.store.logo_url,
            },
            'product': None
        }
        if reel.product:
            data['product'] = {
                'id': reel.product.id,
                'name': reel.product.name,
                'price': reel.product.price,
                'is_offer': reel.product.is_offer,
                'original_price': reel.product.original_price,
                'stock_quantity': reel.product.stock_quantity,
            }
        return data
