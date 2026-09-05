import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app, request
from shared.time_utils import current_time
from database import db
from shared.validators import is_strong_password, is_valid_email, is_valid_phone_syrian

# استيراد Cloudinary
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# ========== دوال عامة ==========

def generate_public_id():
    """توليد معرف عام فريد للمستخدم."""
    import string
    import secrets
    from models import User
    chars = string.ascii_uppercase + string.digits
    while True:
        pid = f"A-{''.join(secrets.choice(chars) for _ in range(4))}-{''.join(secrets.choice(chars) for _ in range(4))}"
        if not User.query.filter_by(public_id=pid).first():
            return pid

def get_upload_path(filename):
    """تحويل اسم الملف المخزن إلى مسار مطلق (للملفات المحلية القديمة)."""
    if not filename:
        return None
    if filename.startswith('http'):
        return None
    if filename.startswith('uploads/'):
        return os.path.join(current_app.config['UPLOAD_FOLDER'], filename[len('uploads/'):])
    return os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

def get_setting(key, default=None):
    """جلب قيمة إعداد من جدول الإعدادات."""
    from models import Setting
    setting = Setting.query.filter_by(key=key).first()
    return setting.value if setting else default

def set_setting(key, value):
    """تحديث أو إنشاء إعداد."""
    from models import Setting
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()
    return True

def is_store_open(store):
    """التحقق من أن المتجر مفتوح الآن وفقًا لساعات العمل."""
    if not store.working_hours or '-' not in store.working_hours:
        return False
    try:
        parts = store.working_hours.split('-')
        if len(parts) != 2:
            return False
        open_time = parts[0].strip()
        close_time = parts[1].strip()

        def time_to_minutes(t):
            h, m = t.split(':')
            return int(h) * 60 + int(m)

        open_min = time_to_minutes(open_time)
        close_min = time_to_minutes(close_time)
        now = current_time()
        current_min = now.hour * 60 + now.minute

        if open_min <= close_min:
            return open_min <= current_min <= close_min
        else:
            return current_min >= open_min or current_min <= close_min
    except (ValueError, AttributeError):
        return False

def is_store_active(store):
    """التحقق من أن المتجر نشط ولديه اشتراك ساري المفعول."""
    from models import Subscription
    if store.subscription_status != 'active':
        return False
    paid_sub = Subscription.query.filter_by(store_id=store.id, status='paid') \
        .order_by(Subscription.end_date.desc()).first()
    if not paid_sub or paid_sub.end_date < current_time():
        return False
    return True

def safe_redirect_target(target):
    """التحقق من أن رابط إعادة التوجيه آمن."""
    if target and target.startswith('/') and not target.startswith('//'):
        return target
    return None

def safe_referrer():
    """إرجاع رابط الرجوع الآمن إذا كان من نفس الموقع."""
    from urllib.parse import urlparse
    referrer = request.referrer
    if not referrer:
        return None
    parsed = urlparse(referrer)
    if parsed.netloc == request.host or parsed.netloc == '':
        path = parsed.path
        if path.startswith('/') and not path.startswith('//'):
            if parsed.query:
                return f"{path}?{parsed.query}"
            return path
    return None

# ========== حفظ الملفات ==========

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi'}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024

def _secure_file(file, allowed_extensions, max_size):
    if not file or file.filename == '':
        return None
    # استخراج الامتداد من الاسم الأصلي قبل secure_filename
    original_filename = file.filename
    if '.' in original_filename:
        ext = original_filename.rsplit('.', 1)[1].lower()
    else:
        ext = ''
    if ext not in allowed_extensions:
        return None
    mimetype = file.mimetype or ''
    if mimetype.startswith('image/') and ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    if mimetype.startswith('video/') and ext not in ALLOWED_VIDEO_EXTENSIONS:
        return None
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > max_size:
        return None
    return ext

def delete_cloudinary_file(url):
    """حذف ملف من Cloudinary باستخدام public_id المستخرج من الرابط."""
    if not url or not url.startswith('http'):
        return
    try:
        # تحليل الرابط لاستخراج public_id
        # مثال: https://res.cloudinary.com/cloud_name/image/upload/v1234567890/folder/file.jpg
        parts = url.split('/')
        # البحث عن 'upload' لتحديد بداية المسار
        if 'upload' not in parts:
            return
        idx = parts.index('upload')
        # الأجزاء بعد 'upload' قد تحتوي على version مثل v1234567890
        path_parts = parts[idx+1:]
        # إزالة أرقام الإصدار (v...)
        filtered = [p for p in path_parts if not (p.startswith('v') and p[1:].isdigit())]
        # إزالة اسم الملف والامتداد من النهاية
        if filtered:
            filename = filtered[-1]
            public_id_with_ext = '/'.join(filtered[:-1] + [filename.rsplit('.', 1)[0]]) if '.' in filename else '/'.join(filtered)
        else:
            return
        cloudinary.uploader.destroy(public_id_with_ext)
    except Exception as e:
        current_app.logger.error(f"Failed to delete old Cloudinary file: {e}")

def save_image(file, old_url=None):
    ext = _secure_file(file, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE)
    if not ext:
        raise ValueError('صيغة الملف غير مدعومة أو الحجم كبير جداً')
    try:
        file.seek(0)
        upload_result = cloudinary.uploader.upload(
            file,
            folder="husayniyyah_market/uploads",
            resource_type="image",
            quality="auto:good",
            fetch_format="auto"
        )
        new_url = upload_result.get('secure_url')
        if new_url and old_url:
            delete_cloudinary_file(old_url)
        return new_url
    except Exception as e:
        current_app.logger.error(f'save_image failed: {str(e)}')
        raise ValueError(f'فشل رفع الصورة إلى Cloudinary: {str(e)}')

def save_video(file, old_url=None):
    ext = _secure_file(file, ALLOWED_VIDEO_EXTENSIONS, MAX_VIDEO_SIZE)
    if not ext:
        raise ValueError('صيغة الفيديو غير مدعومة أو الحجم كبير جداً')
    try:
        file.seek(0)
        upload_result = cloudinary.uploader.upload(
            file,
            folder="husayniyyah_market/videos",
            resource_type="video",
            chunk_size=6000000,
            timeout=120
        )
        new_url = upload_result.get('secure_url')
        if new_url and old_url:
            delete_cloudinary_file(old_url)
        return new_url
    except Exception as e:
        current_app.logger.error(f'save_video failed: {str(e)}')
        raise ValueError(f'فشل رفع الفيديو إلى Cloudinary: {str(e)}')
