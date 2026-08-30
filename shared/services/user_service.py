from database import db
import models
from werkzeug.security import generate_password_hash
from utils import is_strong_password
import secrets
import string
import os
from utils import get_upload_path

class UserService:
    @staticmethod
    def toggle_user_status(user_id, admin_user_id=None):
        """
        تبديل حالة المستخدم (نشط/محظور) مع مراعاة عدم حظر آخر مدير نشط.
        يرجع (success: bool, message: str, updated_user: models.User أو None)
        """
        target = models.User.query.get_or_404(user_id)
        if admin_user_id and target.id == admin_user_id:
            return False, 'لا يمكنك حظر نفسك', None

        if target.role == 'admin' and target.is_active:
            active_admins = models.User.query.filter_by(role='admin', is_active=True).count()
            if active_admins <= 1:
                return False, 'لا يمكنك حظر آخر مسؤول نشط', None

        target.is_active = not target.is_active
        db.session.commit()
        return True, f'تم تحديث حالة المستخدم {target.username}', target

    @staticmethod
    def delete_user_fully(user_id, admin_user_id=None):
        """
        حذف مستخدم وجميع بياناته المرتبطة (طلبات، متاجر، منتجات، ملفات).
        يعتمد على cascade في قاعدة البيانات لحذف العلاقات تلقائيًا.
        """
        target = models.User.query.get_or_404(user_id)
        if admin_user_id and target.id == admin_user_id:
            return False, 'لا يمكنك حذف حسابك الحالي'
        if target.role == 'admin' and target.is_active:
            active_admins = models.User.query.filter_by(role='admin', is_active=True).count()
            if active_admins <= 1:
                return False, 'لا يمكن حذف آخر مدير نشط'

        try:
            # جمع قائمة الملفات المراد حذفها
            files_to_delete = []

            # الصورة الشخصية
            if target.avatar:
                files_to_delete.append(target.avatar)

            # صور وفيديوهات المنتجات في متاجر المستخدم
            stores = models.Store.query.filter_by(owner_id=target.id).all()
            for store in stores:
                products = models.Product.query.filter_by(store_id=store.id).all()
                for product in products:
                    if product.images:
                        for img in product.images.split(','):
                            img = img.strip()
                            if img:
                                files_to_delete.append(img)
                    if product.video:
                        files_to_delete.append(product.video)

            # حذف المستخدم (cascade يتكفل بالباقي)
            db.session.delete(target)
            db.session.commit()

            # حذف الملفات من القرص بعد نجاح العملية
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
        """
        إعادة تعيين كلمة مرور لمستخدم وإنشاء كلمة مؤقتة قوية.
        يرجع (success, message, temp_password)
        """
        target = models.User.query.get_or_404(user_id)
        while True:
            temp_password = 'Aa1' + secrets.token_urlsafe(6)
            strong, msg = is_strong_password(temp_password)
            if strong:
                break
        target.password_hash = generate_password_hash(temp_password)
        db.session.commit()
        return True, f'تم إعادة تعيين كلمة مرور المستخدم {target.username}', temp_password
