import re
import string

def is_valid_email(email):
    """التحقق من صحة البريد الإلكتروني."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone_syrian(phone):
    """التحقق من رقم هاتف سوري (9 أرقام يبدأ بـ 9)."""
    if not phone:
        return False
    phone = phone.strip()
    if phone.startswith('+963'):
        phone = phone[4:]
    elif phone.startswith('963'):
        phone = phone[3:]
    elif phone.startswith('0'):
        phone = phone[1:]
    return len(phone) == 9 and phone.startswith('9') and phone.isdigit()

def is_strong_password(password):
    """التحقق من قوة كلمة المرور: طول >=8، حرف كبير، حرف صغير، رقم، رمز خاص."""
    if len(password) < 8:
        return False, 'كلمة المرور يجب أن تكون 8 أحرف على الأقل'
    if not any(c.isupper() for c in password):
        return False, 'كلمة المرور يجب أن تحتوي على حرف كبير (A-Z)'
    if not any(c.islower() for c in password):
        return False, 'كلمة المرور يجب أن تحتوي على حرف صغير (a-z)'
    if not any(c.isdigit() for c in password):
        return False, 'كلمة المرور يجب أن تحتوي على رقم (0-9)'
    if not any(c in string.punctuation for c in password):
        return False, 'كلمة المرور يجب أن تحتوي على رمز خاص مثل !@#$%^&*()'
    return True, ''
