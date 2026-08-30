from database import db
import models
from flask import url_for
from time_utils import current_time
from utils import save_image, get_upload_path, get_setting
from datetime import timedelta
from services.payment_service import PaymentService
from services.notification_service import NotificationService
import os
import random
import string
import secrets

class SubscriptionService:
    @staticmethod
    def approve_subscription(sub_id):
        sub = models.Subscription.query.get_or_404(sub_id)
        try:
            sub.status = 'paid'
            sub.start_date = current_time()
            sub.end_date = current_time() + timedelta(days=30)
            db.session.add(sub)

            if sub.store_id:
                store = db.session.get(models.Store, sub.store_id)
                if store:
                    store.subscription_status = 'active'
                    store.subscription_expiry = sub.end_date
                    db.session.add(store)

            if sub.user:
                NotificationService.send_to_user(
                    user_id=sub.user.id,
                    message='تم تفعيل اشتراك متجرك بنجاح',
                    link=f'/store/{sub.store_id}' if sub.store_id else '/dashboard',
                    type_=NotificationService.TYPE_SUBSCRIPTION,
                    priority=NotificationService.PRIORITY_IMPORTANT
                )

            payments = models.Payment.query.filter_by(subscription_id=sub.id).all()
            for p in payments:
                if p.status == 'pending':
                    p.status = 'paid'

            db.session.commit()
            return True, 'تمت الموافقة على الاشتراك'
        except Exception as e:
            db.session.rollback()
            return False, 'حدث خطأ أثناء الموافقة على الاشتراك'

    @staticmethod
    def reject_subscription(sub_id):
        sub = models.Subscription.query.get_or_404(sub_id)
        try:
            sub.status = 'cancelled'
            db.session.add(sub)

            if sub.store_id:
                store = db.session.get(models.Store, sub.store_id)
                if store:
                    store.subscription_status = 'cancelled'
                    store.subscription_expiry = None
                    db.session.add(store)

            if sub.user:
                NotificationService.send_to_user(
                    user_id=sub.user.id,
                    message='تم رفض طلب اشتراك المتجر، يرجى التواصل مع الإدارة',
                    link=f'/store/{sub.store_id}/subscription' if sub.store_id else '/dashboard',
                    type_=NotificationService.TYPE_SUBSCRIPTION,
                    priority=NotificationService.PRIORITY_URGENT
                )

            payments = models.Payment.query.filter_by(subscription_id=sub.id).all()
            for p in payments:
                if p.status == 'pending':
                    p.status = 'failed'

            db.session.commit()
            return True, 'تم رفض طلب الاشتراك'
        except Exception:
            db.session.rollback()
            return False, 'حدث خطأ أثناء رفض الاشتراك'

    @staticmethod
    def check_expiring_subscriptions(days=3):
        threshold = current_time() + timedelta(days=days)
        expiring_subs = models.Subscription.query.filter(
            models.Subscription.status == 'paid',
            models.Subscription.end_date > current_time(),
            models.Subscription.end_date <= threshold,
            models.Subscription.expiry_notified == False
        ).all()
        for sub in expiring_subs:
            if sub.store and sub.store.owner_id:
                owner = db.session.get(models.User, sub.store.owner_id)
                if owner:
                    NotificationService.send_to_user(
                        user_id=owner.id,
                        title='تنبيه انتهاء الاشتراك',
                        message=f'سينتهي اشتراك متجرك "{sub.store.name}" بتاريخ {sub.end_date.strftime("%Y-%m-%d")}. يرجى التجديد لتجنب انقطاع الخدمة.',
                        link=url_for('store.store_subscription', store_id=sub.store.id),
                        type_=NotificationService.TYPE_SUBSCRIPTION,
                        priority=NotificationService.PRIORITY_URGENT
                    )
            sub.expiry_notified = True
            db.session.add(sub)
        if expiring_subs:
            db.session.commit()
        return len(expiring_subs)

    @staticmethod
    def submit_subscription_request(user, store, payment_ref=None, proof_file=None, payment_method='wallet'):
        try:
            subscription_price = float(get_setting('subscription_price', 500))
        except (TypeError, ValueError):
            subscription_price = 500.0

        # التحقق من ملكية المتجر
        if store.owner_id != user.id:
            return False, 'غير مسموح لك بتقديم طلب اشتراك لهذا المتجر', None

        sub = models.Subscription.query.filter_by(store_id=store.id, status='pending').first()

        if sub and sub.status == 'paid' and sub.end_date > current_time():
            return False, 'اشتراكك نشط، يمكنك التجديد عند انتهائه', None

        if not sub:
            sub = models.Subscription(
                user_id=user.id,
                store_id=store.id,
                start_date=current_time(),
                end_date=current_time() + timedelta(days=30),
                amount=subscription_price,
                status='pending',
                payment_ref=None
            )
            db.session.add(sub)

        sub.amount = subscription_price
        sub.start_date = current_time()
        sub.status = 'pending'
        sub.payment_method = payment_method

        try:
            if payment_method == 'manual_delivery':
                sub.payment_ref = None
                if not sub.confirmation_code:
                    sub.confirmation_code = ''.join(secrets.choice('0123456789') for _ in range(6))
                if sub.proof_image:
                    old_proof = get_upload_path(sub.proof_image)
                    if old_proof and os.path.exists(old_proof):
                        try:
                            os.remove(old_proof)
                        except Exception:
                            pass
                    sub.proof_image = None

                # البحث عن دفع معلق قائم لهذا الاشتراك لتحديثه بدلاً من إنشاء جديد
                existing_payment = models.Payment.query.filter_by(
                    subscription_id=sub.id,
                    status='pending',
                    method='manual_delivery'
                ).first()

                if existing_payment:
                    existing_payment.amount = subscription_price
                    existing_payment.reference = sub.confirmation_code
                    existing_payment.proof_image = None
                    existing_payment.notes = 'تسليم يدوي'
                    db.session.add(existing_payment)
                else:
                    payment, err = PaymentService.create_payment(
                        user_id=user.id,
                        amount=subscription_price,
                        method='manual_delivery',
                        subscription_id=sub.id,
                        store_id=store.id,
                        reference=sub.confirmation_code,
                        proof_image=None,
                        notes='تسليم يدوي'
                    )
                    if not payment:
                        raise ValueError(f'تعذر تسجيل الدفع: {err}')

            else:
                if not payment_ref:
                    raise ValueError('يجب إدخال رقم العملية')
                sub.payment_ref = payment_ref
                if proof_file and proof_file.filename != '':
                    new_proof = save_image(proof_file)
                    if new_proof:
                        if sub.proof_image:
                            old_proof = get_upload_path(sub.proof_image)
                            if old_proof and os.path.exists(old_proof):
                                try:
                                    os.remove(old_proof)
                                except Exception:
                                    pass
                        sub.proof_image = new_proof

                # البحث عن دفع معلق قائم لهذا الاشتراك
                existing_payment = models.Payment.query.filter_by(
                    subscription_id=sub.id,
                    status='pending'
                ).first()

                if existing_payment:
                    existing_payment.amount = subscription_price
                    existing_payment.method = payment_method
                    existing_payment.reference = payment_ref
                    existing_payment.proof_image = sub.proof_image
                    existing_payment.notes = 'اشتراك متجر'
                    db.session.add(existing_payment)
                else:
                    payment, err = PaymentService.create_payment(
                        user_id=user.id,
                        amount=subscription_price,
                        method=payment_method,
                        subscription_id=sub.id,
                        store_id=store.id,
                        reference=payment_ref,
                        proof_image=sub.proof_image,
                        notes='اشتراك متجر'
                    )
                    if not payment:
                        raise ValueError(f'تعذر تسجيل الدفع: {err}')

            db.session.commit()
            return True, 'تم إرسال طلب الاشتراك بنجاح', sub
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def verify_manual_confirmation(user, sub_id, code):
        sub = models.Subscription.query.get_or_404(sub_id)
        if sub.user_id != user.id:
            return False, 'غير مسموح'
        if sub.payment_method != 'manual_delivery':
            return False, 'طريقة الدفع غير صحيحة'
        if sub.status != 'pending':
            return False, 'الاشتراك ليس قيد الانتظار'
        if not sub.confirmation_code or sub.confirmation_code != code.strip():
            return False, 'كود التأكيد غير صحيح'

        try:
            sub.status = 'paid'
            sub.start_date = current_time()
            sub.end_date = current_time() + timedelta(days=30)
            db.session.add(sub)

            if sub.store_id:
                store = db.session.get(models.Store, sub.store_id)
                if store:
                    store.subscription_status = 'active'
                    store.subscription_expiry = sub.end_date
                    db.session.add(store)

            payments = models.Payment.query.filter_by(subscription_id=sub.id).all()
            for p in payments:
                if p.status == 'pending':
                    p.status = 'paid'

            db.session.commit()
            return True, 'تم تفعيل اشتراك متجرك بنجاح'
        except Exception:
            db.session.rollback()
            return False, 'حدث خطأ أثناء التفعيل'
