from database import db
from flask import url_for
import models
import random
from time_utils import current_time
from delivery_utils import is_delivery_available
from services.notification_service import NotificationService
from services.payment_service import PaymentService
from utils import get_setting, is_store_active

class OrderService:
    @staticmethod
    def generate_delivery_code():
        """توليد رمز تسليم مكون من 6 أرقام."""
        return ''.join(random.choices('0123456789', k=6))

    @staticmethod
    def _check_store_active(store):
        """التحقق من أن المتجر نشط واشتراكه مدفوع وغير منتهي."""
        if not is_store_active(store):
            raise ValueError('هذا المتجر غير نشط حالياً ولا يمكن الطلب منه')

    @staticmethod
    def create_order(user, store, cart_items=None, items_data=None, delivery_address=None,
                     latitude=None, longitude=None, payment_method='cash'):
        """
        إنشاء طلب جديد.
        """
        if not user or not store:
            raise ValueError("بيانات الطلب غير مكتملة")

        OrderService._check_store_active(store)

        order_items = []
        if cart_items is not None:
            for item in cart_items:
                if 'product' not in item or 'quantity' not in item:
                    raise ValueError('بيانات السلة غير صحيحة')
                product = item['product']
                qty = item['quantity']
                if not product or product.store_id != store.id:
                    raise ValueError(f"المنتج {product.name if product else 'غير معروف'} لا يخص هذا المتجر")
                order_items.append((product, qty))
        elif items_data is not None:
            for item in items_data:
                product_id = item.get('product_id')
                qty = item.get('quantity', 1)
                if not product_id or qty <= 0:
                    raise ValueError('بيانات المنتج غير صحيحة')
                product = db.session.get(models.Product, product_id)
                if not product:
                    raise ValueError(f'المنتج رقم {product_id} غير موجود')
                if product.store_id != store.id:
                    raise ValueError('يجب أن تكون جميع المنتجات من نفس المتجر')
                order_items.append((product, qty))
        else:
            raise ValueError("يجب توفير cart_items أو items_data")

        if not order_items:
            raise ValueError('لا توجد منتجات صالحة في الطلب')

        for product, qty in order_items:
            if product.stock_quantity < qty:
                raise ValueError(f"المخزون غير كافٍ للمنتج {product.name}")

        product_total = sum(product.price * qty for product, qty in order_items)
        delivery_fee = float(get_setting('delivery_fee', 100)) if store.has_delivery else 0.0
        grand_total = product_total + delivery_fee

        if store.has_delivery and not delivery_address:
            raise ValueError("العنوان مطلوب لخدمة التوصيل")

        order = models.Order(
            customer_id=user.id,
            store_id=store.id,
            status='new',
            total=grand_total,
            delivery_fee=delivery_fee,
            delivery_code=OrderService.generate_delivery_code(),
            delivery_address=delivery_address if store.has_delivery else None,
            latitude=latitude if store.has_delivery else None,
            longitude=longitude if store.has_delivery else None,
            is_cancelled=False,
            payment_method=payment_method
        )
        db.session.add(order)
        db.session.flush()

        # إنشاء سجل دفع
        PaymentService.create_payment(
            user_id=user.id,
            amount=grand_total,
            method=payment_method,
            order_id=order.id,
            store_id=store.id,
            reference=None,
            proof_image=None,
            notes='طلب جديد'
        )

        for product, qty in order_items:
            product.stock_quantity -= qty
            db.session.add(product)
            order_item = models.OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                price=product.price,
                options_selected=None
            )
            db.session.add(order_item)

        NotificationService.send_to_store_owner(
            store,
            f"طلب جديد رقم {order.id} من {user.username}",
            link=f"/store/{store.id}/orders"
        )

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise ValueError('حدث خطأ أثناء إنشاء الطلب، حاول مرة أخرى')
        return order

    @staticmethod
    def cancel_order(user, order):
        if order.customer_id != user.id:
            raise PermissionError("لا يمكنك إلغاء هذا الطلب")
        if order.status != 'new':
            raise ValueError("لا يمكن إلغاء هذا الطلب في حالته الحالية")

        for item in order.items:
            product = item.product
            if product:
                product.stock_quantity += item.quantity
                db.session.add(product)

        order.status = 'cancelled'
        order.is_cancelled = True
        db.session.add(order)

        if order.store:
            NotificationService.send_to_store_owner(
                order.store,
                f"تم إلغاء الطلب رقم {order.id} من الزبون {user.username}",
                link=f"/store/{order.store.id}/orders"
            )

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise ValueError('حدث خطأ أثناء إلغاء الطلب')
        return order

    @staticmethod
    def start_delivery(delivery_user, order):
        if order.delivery_person_id != delivery_user.id:
            raise PermissionError("هذا الطلب غير مخصص لك")
        if order.status != 'ready':
            raise ValueError("لا يمكن بدء التسليم الآن")

        order.status = 'delivering'
        db.session.add(order)

        if order.store:
            NotificationService.send_to_store_owner(
                order.store,
                f"بدأ المندوب {delivery_user.username} بتسليم الطلب رقم {order.id}",
                link=f"/store/{order.store.id}/orders"
            )

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise ValueError('حدث خطأ أثناء بدء التسليم')
        return order

    @staticmethod
    def complete_delivery(delivery_user, order, delivery_code):
        if order.delivery_person_id != delivery_user.id:
            raise PermissionError("هذا الطلب غير مخصص لك")
        if order.status != 'delivering':
            raise ValueError("لا يمكن التسليم الآن")
        if delivery_code != order.delivery_code:
            raise ValueError("رمز التسليم غير صحيح")

        order.status = 'delivered'
        order.delivered_at = current_time()
        db.session.add(order)

        if order.store:
            NotificationService.send_to_store_owner(
                order.store,
                f"تم تسليم الطلب رقم {order.id} بنجاح",
                link=f"/store/{order.store.id}/orders"
            )

        if order.customer_id:
            NotificationService.send_to_user(
                order.customer_id,
                f"تم تسليم طلبك رقم {order.id} بنجاح",
                link="/cart",
                type_=NotificationService.TYPE_ORDER
            )

        payments = models.Payment.query.filter_by(order_id=order.id).all()
        for p in payments:
            if p.status == 'pending' and p.method == 'cash':
                p.status = 'paid'

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise ValueError('حدث خطأ أثناء تأكيد التسليم')
        return order

    @staticmethod
    def update_order_status_by_store(user, store, order, new_status,
                                     delivery_person_id=None, notify_delivery=False):
        if order.store_id != store.id:
            return None, 'هذا الطلب لا يخص متجرك'

        # التحقق من نشاط المتجر
        if not is_store_active(store):
            return None, 'متجرك غير نشط حالياً، لا يمكنك تحديث الطلبات'

        if order.status == 'cancelled':
            return None, 'هذا الطلب ملغي ولا يمكن تغيير حالته'

        allowed_statuses = ['confirmed', 'preparing', 'ready', 'delivering', 'cancelled']
        if new_status not in allowed_statuses:
            return None, 'حالة غير صالحة'

        if delivery_person_id:
            person = db.session.get(models.User, delivery_person_id)
            if not person or not is_delivery_available(person):
                return None, 'المندوب غير متاح حالياً'
            if not store.has_delivery:
                return None, 'هذا المتجر لا يوفر خدمة توصيل'

            if order.delivery_person_id is None:
                order.delivery_fee = float(get_setting('delivery_fee', 100))
            order.delivery_person_id = person.id

            if notify_delivery:
                NotificationService.send_to_user(
                    user_id=person.id,
                    message=f'تم إسناد الطلب رقم {order.id} إليك من متجر {store.name}',
                    link=url_for('delivery.delivery_dashboard'),
                    type_=NotificationService.TYPE_DELIVERY,
                    priority=NotificationService.PRIORITY_IMPORTANT
                )
        else:
            if new_status in ['confirmed', 'preparing']:
                order.delivery_person_id = None
                order.delivery_fee = 0.0

        if new_status == 'cancelled' and order.status != 'cancelled':
            for item in order.items:
                product = item.product
                if product:
                    product.stock_quantity += item.quantity
                    db.session.add(product)

        order.status = new_status
        if new_status == 'cancelled':
            order.is_cancelled = True
        db.session.add(order)

        if order.customer_id:
            customer = db.session.get(models.User, order.customer_id)
            if customer:
                NotificationService.send_to_user(
                    user_id=customer.id,
                    message=f'تحديث لحالة طلبك رقم {order.id} من متجر {store.name}: {new_status}',
                    link=url_for('cart.cart'),
                    type_=NotificationService.TYPE_ORDER
                )

        if new_status == 'delivered':
            payments = models.Payment.query.filter_by(order_id=order.id).all()
            for p in payments:
                if p.status == 'pending' and p.method == 'cash':
                    p.status = 'paid'

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return None, 'حدث خطأ أثناء تحديث الطلب'
        return order, None
