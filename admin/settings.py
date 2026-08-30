from flask import render_template, request, redirect, url_for, flash
from utils import get_setting, set_setting
from decorators import role_required
from . import admin_bp

@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@role_required('admin')
def admin_settings():
    if request.method == 'POST':
        subscription_price = request.form.get('subscription_price', '').strip()
        wallet_number = request.form.get('wallet_number', '').strip()
        delivery_fee = request.form.get('delivery_fee', '').strip()

        if subscription_price:
            try:
                price = float(subscription_price)
                if price <= 0:
                    flash('يجب أن يكون سعر الاشتراك أكبر من صفر', 'error')
                else:
                    set_setting('subscription_price', str(price))
                    flash('تم تحديث سعر الاشتراك', 'success')
            except ValueError:
                flash('قيمة غير صالحة لسعر الاشتراك', 'error')

        if wallet_number:
            set_setting('wallet_number', wallet_number)
            flash('تم تحديث رقم المحفظة', 'success')

        if delivery_fee:
            try:
                fee = float(delivery_fee)
                if fee < 0:
                    flash('رسوم التوصيل لا يمكن أن تكون سالبة', 'error')
                else:
                    set_setting('delivery_fee', str(fee))
                    flash('تم تحديث رسوم التوصيل', 'success')
            except ValueError:
                flash('قيمة غير صالحة لرسوم التوصيل', 'error')

        return redirect(url_for('admin.admin_settings'))

    current_price = get_setting('subscription_price', '500')
    try:
        current_price = float(current_price)
    except (TypeError, ValueError):
        current_price = 500.0

    wallet_number = get_setting('wallet_number', '0995680223')
    delivery_fee = get_setting('delivery_fee', '100')
    try:
        delivery_fee = float(delivery_fee)
    except (TypeError, ValueError):
        delivery_fee = 100.0

    return render_template('admin/admin_settings.html',
                           subscription_price=current_price,
                           wallet_number=wallet_number,
                           delivery_fee=delivery_fee)
