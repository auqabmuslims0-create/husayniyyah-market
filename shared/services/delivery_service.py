from database import db
import models
from datetime import datetime
from services.user_service import UserService

class DeliveryService:
    @staticmethod
    def toggle_delivery_person(user_id):
        """
        تبديل حالة المندوب (نشط/محظور).
        يرجع (success, message, user)
        """
        person = models.User.query.get_or_404(user_id)
        if person.role != 'delivery':
            return False, 'المستخدم ليس مندوبًا', person
        person.is_active = not person.is_active
        db.session.commit()
        return True, f'تم تحديث حالة المندوب {person.username}', person

    @staticmethod
    def delete_delivery_person(user_id):
        """
        حذف مندوب مع إلغاء إسناد طلباته ثم حذف شامل.
        يرجع (success, message)
        """
        person = models.User.query.get_or_404(user_id)
        if person.role != 'delivery':
            return False, 'المستخدم ليس مندوبًا'
        # إلغاء إسناد الطلبات
        assigned_orders = models.Order.query.filter_by(delivery_person_id=person.id).all()
        for order in assigned_orders:
            order.delivery_person_id = None
            order.delivery_fee = 0.0
            db.session.add(order)
        db.session.commit()

        # حذف شامل للمستخدم
        success, msg = UserService.delete_user_fully(person.id)
        return success, msg

    @staticmethod
    def update_shift(user_id, shift_start_str=None, shift_end_str=None, max_active_orders=None):
        """
        تحديث وردية المندوب.
        يرجع (success, message)
        """
        person = models.User.query.get_or_404(user_id)
        try:
            if shift_start_str:
                person.shift_start_time = datetime.strptime(shift_start_str, '%H:%M').time()
            else:
                person.shift_start_time = None
            if shift_end_str:
                person.shift_end_time = datetime.strptime(shift_end_str, '%H:%M').time()
            else:
                person.shift_end_time = None
            if max_active_orders is not None:
                person.max_active_orders = int(max_active_orders)
            db.session.commit()
            return True, 'تم تحديث الوردية'
        except Exception:
            db.session.rollback()
            return False, 'بيانات غير صالحة'
