from database import db
from models import User
from shared.repositories.user_repository import UserRepository
from werkzeug.security import generate_password_hash
from shared.utils import is_strong_password, get_upload_path
import secrets
import os

class UserService:
    @staticmethod
    def toggle_user_status(user_id, admin_user_id=None):
        target = UserRepository.get_by_id(user_id)
        if not target:
            raise ValueError('المستخدم غير موجود')
        if admin_user_id and target.id == admin_user_id:
            return False, 'لا يمكنك حظر نفسك', None

        if target.role == 'admin' and target.is_active:
            active_admins = UserRepository.get_active_admins_count()
            if active_admins <= 1:
                return False, 'لا يمكنك حظر آخر مسؤول نشط', None

        UserRepository.toggle_active(target)
        db.session.commit()
        return True, f'تم تحديث حالة المستخدم {target.username}', target

    @staticmethod
    def delete_user_fully(user_id, admin_user_id=None):
        target = UserRepository.get_by_id(user_id)
        if not target:
            return False, 'المستخدم غير موجود'
        if admin_user_id and target.id == admin_user_id:
            return False, 'لا يمكنك حذف حسابك الحالي'
        if target.role == 'admin' and target.is_active:
            active_admins = UserRepository.get_active_admins_count()
            if active_admins <= 1:
                return False, 'لا يمكن حذف آخر مدير نشط'

        try:
            files_to_delete = []
            if target.avatar:
                files_to_delete.append(target.avatar)

            # جمع ملفات المنتجات من متاجر المستخدم
            stores = target.stores
            for store in stores:
                for product in store.products:
                    if product.images:
                        for img in product.images.split(','):
                            img = img.strip()
                            if img:
                                files_to_delete.append(img)
                    if product.video:
                        files_to_delete.append(product.video)

            UserRepository.delete(target)
            db.session.commit()

            for filename in files_to_delete:
                file_path = get_upload_path(filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

            return True, 'تم حذف المستخدم وجميع بياناته بنجاح'
        except Exception as e:
            db.session.rollback()
            return False, f'حدث خطأ أثناء الحذف: {str(e)}'

    @staticmethod
    def reset_password(user_id):
        target = UserRepository.get_by_id(user_id)
        if not target:
            return False, 'المستخدم غير موجود', None
        while True:
            temp_password = 'Aa1' + secrets.token_urlsafe(6)
            strong, msg = is_strong_password(temp_password)
            if strong:
                break
        target.password_hash = generate_password_hash(temp_password)
        db.session.commit()
        return True, f'تم إعادة تعيين كلمة مرور المستخدم {target.username}', temp_password
