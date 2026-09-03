from database import db
from services.notification_service import NotificationService
import models
from utils import get_upload_path, is_store_active, get_setting
from time_utils import current_time
from datetime import timedelta
import os

class StoreService:
    @staticmethod
    def _create_admin_subscription(store):
        """إنشاء اشتراك إداري مجاني عند التفعيل اليدوي من المدير."""
        duration_days = int(get_setting('subscription_duration_days', 30))
        sub = models.Subscription(
            user_id=store.owner_id,
            store_id=store.id,
            start_date=current_time(),
            end_date=current_time() + timedelta(days=duration_days),
            amount=0.0,
            status='paid',
            payment_method='manual_delivery',
            payment_ref=None,
            proof_image=None,
            confirmation_code=None,
            duration_days=duration_days,
            renewal_count=0,
            expiry_notified=False
        )
        db.session.add(sub)
        db.session.flush()  # للحصول على معرف الاشتراك وتحديث الجلسة
        return sub

    @staticmethod
    def toggle_store_status(store_id, force_activate=False):
        """
        تبديل حالة المتجر بين نشط ومعلق.
        يرجع (success, message, store)

        :param store_id: معرف المتجر
        :param force_activate: إذا كان True، يتم التفعيل حتى بدون اشتراك ساري
        """
        store = models.Store.query.get_or_404(store_id)

        try:
            if store.subscription_status == 'active':
                # تعليق المتجر
                store.subscription_status = 'suspended'
                action = 'تم تعليق المتجر'
            elif store.subscription_status in ['suspended', 'cancelled', 'expired']:
                if force_activate:
                    # تفعيل إداري: السماح بالتفعيل وإنشاء اشتراك مجاني إذا لزم
                    if not is_store_active(store):
                        # لا يوجد اشتراك ساري، ننشئ اشتراكًا إداريًا مجانيًا
                        sub = StoreService._create_admin_subscription(store)
                        store.subscription_status = 'active'
                        store.subscription_expiry = sub.end_date
                    else:
                        # يوجد اشتراك ساري بالفعل، نكتفي بتفعيل المتجر
                        store.subscription_status = 'active'
                    action = 'تم تفعيل المتجر (تفعيل إداري)'
                else:
                    # تفعيل عادي يتطلب اشتراك ساري
                    if not is_store_active(store):
                        return False, 'لا يمكن تفعيل المتجر لعدم وجود اشتراك ساري المفعول', store
                    store.subscription_status = 'active'
                    action = 'تم تفعيل المتجر'
            else:
                return False, 'لا يمكن تنفيذ الإجراء على متجر بحالة "قيد الانتظار"', store

            db.session.commit()

            if store.owner_id:
                owner = db.session.get(models.User, store.owner_id)
                if owner:
                    NotificationService.send_to_user(
                        user_id=owner.id,
                        title='تحديث حالة المتجر',
                        message=f'قام المدير بتغيير حالة متجرك "{store.name}" إلى {store.subscription_status}',
                        link=f'/store/{store.id}',
                        type_=NotificationService.TYPE_ALERT,
                        priority=NotificationService.PRIORITY_IMPORTANT
                    )
                    db.session.commit()
            return True, action, store
        except Exception as e:
            db.session.rollback()
            import logging
            logging.getLogger(__name__).error(f'خطأ في تغيير حالة المتجر {store_id}: {str(e)}')
            return False, 'حدث خطأ غير متوقع أثناء تنفيذ الإجراء', store

    @staticmethod
    def delete_store(store_id):
        """
        حذف متجر وجميع منتجاته وطلباته وملفاته.
        يرجع (success, message)
        """
        store = models.Store.query.get_or_404(store_id)
        try:
            store_orders = models.Order.query.filter_by(store_id=store.id).all()
            for order in store_orders:
                models.OrderItem.query.filter_by(order_id=order.id).delete()
                db.session.delete(order)

            products = models.Product.query.filter_by(store_id=store.id).all()
            for product in products:
                if product.images:
                    for img_name in product.images.split(','):
                        img_name = img_name.strip()
                        if img_name:
                            file_path = get_upload_path(img_name)
                            if file_path and os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                except Exception:
                                    pass
                if product.video:
                    video_path = get_upload_path(product.video)
                    if video_path and os.path.exists(video_path):
                        try:
                            os.remove(video_path)
                        except Exception:
                            pass
                models.ProductReaction.query.filter_by(product_id=product.id).delete()
                models.ProductComment.query.filter_by(product_id=product.id).delete()
                models.Favorite.query.filter_by(product_id=product.id).delete()
                models.Review.query.filter_by(product_id=product.id).delete()
                db.session.delete(product)

            models.Category.query.filter_by(store_id=store.id).delete()
            models.Subscription.query.filter_by(store_id=store.id).delete()
            models.Payment.query.filter_by(store_id=store.id).delete()
            models.Favorite.query.filter_by(store_id=store.id).delete()
            db.session.delete(store)
            db.session.commit()
            return True, 'تم حذف المتجر بنجاح'
        except Exception:
            db.session.rollback()
            return False, 'حدث خطأ أثناء حذف المتجر'
