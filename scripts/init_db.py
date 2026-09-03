import os
import sys

# التأكد من استيراد التطبيق بشكل صحيح
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app, ensure_admin
from database import db
import models  # noqa: F401 لضمان تسجيل النماذج

with app.app_context():
    print("إنشاء الجداول إن لم تكن موجودة...")
    db.create_all()
    print("تم إنشاء الجداول بنجاح.")
    print("إنشاء المدير الافتراضي...")
    ensure_admin()
    print("اكتملت التهيئة.")
