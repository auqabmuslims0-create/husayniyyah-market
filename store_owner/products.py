from flask import render_template, request, redirect, url_for, flash, abort
from database import db
import models
import os
from sqlalchemy.orm import joinedload
from utils import is_store_active, save_image, save_video, get_upload_path
from decorators import role_required
from . import store_bp
from .common import check_store_access

@store_bp.route('/store/<int:store_id>/products')
@role_required('owner')
def store_products(store_id):
    result = check_store_access(store_id)
    if result[0] is None:
        return result[1]
    user, store = result

    q = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', type=int)

    query = models.Product.query.filter_by(store_id=store.id).options(joinedload(models.Product.category))
    if q:
        query = query.filter(models.Product.name.ilike(f'%{q}%'))
    if category_id:
        query = query.filter_by(category_id=category_id)

    products = query.order_by(models.Product.created_at.desc()).all()
    categories = models.Category.query.filter_by(store_id=store.id).all()
    total_products_value = sum(p.price if p.price is not None else 0 for p in products)

    return render_template('store_owner/product_list.html',
                           store=store,
                           products=products,
                           categories=categories,
                           q=q,
                           selected_category=category_id,
                           total_products_value=total_products_value)

@store_bp.route('/store/<int:store_id>/products/new', methods=['GET', 'POST'])
@role_required('owner')
def new_product(store_id):
    result = check_store_access(store_id)
    if result[0] is None:
        return result[1]
    user, store = result

    if not is_store_active(store):
        flash('هذا المتجر غير نشط، يجب دفع الاشتراك')
        return redirect(url_for('store.store_subscription', store_id=store.id))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        product_code = request.form.get('product_code', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', type=float)
        stock_quantity = request.form.get('stock_quantity', type=int, default=0)
        category_id = request.form.get('category_id')
        options = request.form.get('options', '').strip()

        is_offer = request.form.get('is_offer') == 'yes'
        offer_price = request.form.get('offer_price', type=float)
        original_price = request.form.get('original_price', type=float)
        offer_description = request.form.get('offer_description', '').strip()

        if not name or price is None:
            flash('اسم المنتج والسعر مطلوبان')
            return redirect(url_for('store.new_product', store_id=store.id))

        if price < 0 or stock_quantity < 0:
            flash('القيم لا يمكن أن تكون سالبة')
            return redirect(url_for('store.new_product', store_id=store.id))

        category = None
        if category_id:
            category = db.session.get(models.Category, int(category_id))
            if not category or category.store_id != store.id:
                flash('التصنيف غير صالح')
                return redirect(url_for('store.new_product', store_id=store.id))

        # حفظ الصورة الأساسية
        main_image = None
        main_file = request.files.get('main_image')
        if main_file and main_file.filename != '':
            main_image = save_image(main_file)
            if not main_image:
                flash('صيغة الصورة الأساسية غير مدعومة أو الحجم كبير', 'error')
                return redirect(url_for('store.new_product', store_id=store.id))

        # حفظ الصور الفرعية (حتى 4)
        sub_images = []
        uploaded_files = request.files.getlist('sub_images')
        for file in uploaded_files:
            if len(sub_images) >= 4:
                break
            if file and file.filename != '':
                saved_name = save_image(file)
                if saved_name:
                    sub_images.append(saved_name)

        # حفظ الفيديو
        video_file = request.files.get('video')
        video_filename = None
        if video_file and video_file.filename != '':
            video_filename = save_video(video_file)
            if not video_filename:
                flash('صيغة الفيديو غير مدعومة (MP4, MOV, AVI فقط)', 'error')
                return redirect(url_for('store.new_product', store_id=store.id))

        final_price = price
        if is_offer:
            if offer_price is not None and offer_price >= 0:
                final_price = offer_price
            else:
                offer_price = price
                final_price = price
        else:
            offer_price = None
            original_price = None
            offer_description = ''

        product = models.Product(
            store_id=store.id,
            name=name,
            product_code=product_code,
            description=description,
            price=final_price,
            is_offer=is_offer,
            offer_price=offer_price if is_offer else None,
            original_price=original_price if is_offer else None,
            offer_description=offer_description if is_offer else '',
            stock_quantity=stock_quantity,
            category_id=category.id if category else None,
            main_image=main_image,
            sub_images=','.join(sub_images) if sub_images else None,
            video=video_filename,
            options=options
        )
        db.session.add(product)
        db.session.commit()
        flash('تم إضافة المنتج')
        return redirect(url_for('store.store_products', store_id=store.id))

    categories = models.Category.query.filter_by(store_id=store.id).all()
    return render_template('store_owner/product_form.html', store=store, product=None, categories=categories)

@store_bp.route('/store/<int:store_id>/products/<int:product_id>/edit', methods=['GET', 'POST'])
@role_required('owner')
def edit_product(store_id, product_id):
    result = check_store_access(store_id)
    if result[0] is None:
        return result[1]
    user, store = result

    product = models.Product.query.get_or_404(product_id)
    if product.store_id != store.id:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        product_code = request.form.get('product_code', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', type=float)
        stock_quantity = request.form.get('stock_quantity', type=int, default=0)
        category_id = request.form.get('category_id')
        options = request.form.get('options', '').strip()

        is_offer = request.form.get('is_offer') == 'yes'
        offer_price = request.form.get('offer_price', type=float)
        original_price = request.form.get('original_price', type=float)
        offer_description = request.form.get('offer_description', '').strip()

        if not name or price is None:
            flash('اسم المنتج والسعر مطلوبان')
            return redirect(url_for('store.edit_product', store_id=store.id, product_id=product.id))

        if price < 0 or stock_quantity < 0:
            flash('القيم لا يمكن أن تكون سالبة')
            return redirect(url_for('store.edit_product', store_id=store.id, product_id=product.id))

        category = None
        if category_id:
            category = db.session.get(models.Category, int(category_id))
            if not category or category.store_id != store.id:
                flash('التصنيف غير صالح')
                return redirect(url_for('store.edit_product', store_id=store.id, product_id=product.id))

        # الصورة الأساسية
        main_file = request.files.get('main_image')
        if main_file and main_file.filename != '':
            new_main = save_image(main_file)
            if new_main:
                # حذف القديمة إذا وُجدت
                if product.main_image:
                    old_path = get_upload_path(product.main_image)
                    if old_path and os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass
                product.main_image = new_main

        # حذف الصورة الأساسية إذا طُلب
        if request.form.get('remove_main_image') == 'yes':
            if product.main_image:
                old_path = get_upload_path(product.main_image)
                if old_path and os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass
            product.main_image = None

        # الصور الفرعية: نبدأ من القائمة الحالية (إن وُجدت)
        existing_sub = []
        if product.sub_images:
            existing_sub = [img.strip() for img in product.sub_images.split(',') if img.strip()]

        # حذف الصور الفرعية المطلوبة
        remove_sub_images = request.form.getlist('remove_existing_sub_images')
        for img in remove_sub_images:
            if img in existing_sub:
                existing_sub.remove(img)
                # حذف الملف من القرص
                img_path = get_upload_path(img)
                if img_path and os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                    except Exception:
                        pass

        # إضافة صور فرعية جديدة (حتى 4 - الحالي)
        uploaded_files = request.files.getlist('sub_images')
        for file in uploaded_files:
            if len(existing_sub) >= 4:
                break
            if file and file.filename != '':
                saved_name = save_image(file)
                if saved_name:
                    existing_sub.append(saved_name)

        product.sub_images = ','.join(existing_sub) if existing_sub else None

        # الفيديو
        if request.form.get('remove_video') == 'yes':
            if product.video:
                old_video = get_upload_path(product.video)
                if old_video and os.path.exists(old_video):
                    try:
                        os.remove(old_video)
                    except Exception:
                        pass
            product.video = None
        else:
             video_file = request.files.get('video')
             if video_file and video_file.filename != '':
                 new_video = save_video(video_file)
                 if new_video:
                     if product.video:
                         old_video = get_upload_path(product.video)
                         if old_video and os.path.exists(old_video):
                             try:
                                 os.remove(old_video)
                             except Exception:
                                 pass
                     product.video = new_video

        product.name = name
        product.product_code = product_code
        product.description = description
        product.stock_quantity = stock_quantity
        product.category_id = category.id if category else None
        product.options = options

        final_price = price
        if is_offer:
            if offer_price is not None and offer_price >= 0:
                final_price = offer_price
            else:
                offer_price = price
                final_price = price
        else:
            offer_price = None
            original_price = None
            offer_description = ''

        product.price = final_price
        product.is_offer = is_offer
        product.offer_price = offer_price if is_offer else None
        product.original_price = original_price if is_offer else None
        product.offer_description = offer_description if is_offer else ''

        db.session.commit()
        flash('تم حفظ تعديلات المنتج')
        return redirect(url_for('store.store_products', store_id=store.id))

    categories = models.Category.query.filter_by(store_id=store.id).all()
    return render_template('store_owner/product_form.html', store=store, product=product, categories=categories)

@store_bp.route('/store/<int:store_id>/products/<int:product_id>/delete', methods=['POST'])
@role_required('owner')
def delete_product(store_id, product_id):
    result = check_store_access(store_id)
    if result[0] is None:
        return result[1]
    user, store = result

    product = models.Product.query.get_or_404(product_id)
    if product.store_id != store.id:
        abort(403)

    # حذف الصور والفيديو من القرص
    if product.main_image:
        file_path = get_upload_path(product.main_image)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
    if product.sub_images:
        for img in product.sub_images.split(','):
            img = img.strip()
            if img:
                file_path = get_upload_path(img)
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
    if product.video:
        video_path = get_upload_path(product.video)
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass

    db.session.delete(product)
    db.session.commit()
    flash('تم حذف المنتج')
    return redirect(url_for('store.store_products', store_id=store.id))
