from database import db
import models
from time_utils import current_time
from sqlalchemy.orm import joinedload

class PaymentService:
    @staticmethod
    def create_payment(user_id, amount, method='cash', order_id=None, store_id=None, subscription_id=None, reference=None, proof_image=None, notes=None):
        if amount <= 0:
            return None, 'المبلغ يجب أن يكون أكبر من صفر'
        allowed_methods = ['cash', 'wallet', 'bank_transfer', 'manual_delivery']
        if method not in allowed_methods:
            method = 'cash'
        if not user_id:
            return None, 'معرف المستخدم مطلوب'

        payment = models.Payment(
            user_id=user_id,
            order_id=order_id,
            store_id=store_id,
            subscription_id=subscription_id,
            amount=amount,
            method=method,
            status='pending',
            reference=reference,
            proof_image=proof_image,
            notes=notes
        )
        db.session.add(payment)
        return payment, None

    @staticmethod
    def update_payment_status(payment_id, new_status):
        payment = models.Payment.query.get_or_404(payment_id)
        if new_status not in ['pending', 'paid', 'failed', 'refunded']:
            return False, 'حالة غير صالحة'
        payment.status = new_status
        payment.updated_at = current_time()
        try:
            db.session.commit()
            return True, 'تم تحديث حالة الدفع'
        except Exception:
            db.session.rollback()
            return False, 'حدث خطأ أثناء تحديث حالة الدفع'

    @staticmethod
    def get_payment_by_subscription(subscription_id):
        return models.Payment.query.filter_by(subscription_id=subscription_id).all()

    @staticmethod
    def get_payment_by_order(order_id):
        return models.Payment.query.filter_by(order_id=order_id).all()

    @staticmethod
    def get_all_payments(status=None, method=None, page=1, per_page=20):
        query = models.Payment.query.options(
            joinedload(models.Payment.user),
            joinedload(models.Payment.order),
            joinedload(models.Payment.store),
            joinedload(models.Payment.subscription)
        )
        if status:
            query = query.filter(models.Payment.status == status)
        if method:
            query = query.filter(models.Payment.method == method)
        return query.order_by(models.Payment.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
