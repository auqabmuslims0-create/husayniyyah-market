from flask import current_app
from database import db
import models
from time_utils import current_time
from sqlalchemy.orm import joinedload
import json

class NotificationService:
    TYPE_INFO = 'info'
    TYPE_ORDER = 'order'
    TYPE_SUBSCRIPTION = 'subscription'
    TYPE_DELIVERY = 'delivery'
    TYPE_MESSAGE = 'message'
    TYPE_ALERT = 'alert'

    PRIORITY_NORMAL = 'normal'
    PRIORITY_IMPORTANT = 'important'
    PRIORITY_URGENT = 'urgent'

    @staticmethod
    def send_to_user(user_id, message, title=None, link=None, type_=None, priority=None, icon=None, extra_data=None, send_push=True):
        if not user_id:
            return None
        if type_ is None:
            type_ = NotificationService.TYPE_INFO
        if priority is None:
            priority = NotificationService.PRIORITY_NORMAL

        notif = models.Notification(
            user_id=user_id,
            title=title,
            message=message,
            link=link,
            type=type_,
            priority=priority,
            icon=icon,
            extra_data=json.dumps(extra_data) if extra_data else None,
            is_read=False
        )
        db.session.add(notif)
        db.session.flush()  # للحصول على id قبل الإرسال

        if send_push:
            try:
                from shared.services.push_service import send_to_user as push_send_to_user
                push_send_to_user(user_id, notif)
            except Exception as e:
                current_app.logger.error(f"Failed to send push for notification {notif.id}: {e}")

        return notif

    @staticmethod
    def send_to_store_owner(store, message, title=None, link=None, type_=None, priority=None, icon=None, extra_data=None, send_push=True):
        if store and store.owner_id:
            return NotificationService.send_to_user(
                store.owner_id, message, title=title, link=link,
                type_=type_ or NotificationService.TYPE_ORDER,
                priority=priority, icon=icon, extra_data=extra_data,
                send_push=send_push
            )
        return None

    @staticmethod
    def send_to_customer(order, message, title=None, link=None, type_=None, priority=None, icon=None, extra_data=None, send_push=True):
        if order and order.customer_id:
            return NotificationService.send_to_user(
                order.customer_id, message, title=title, link=link,
                type_=type_ or NotificationService.TYPE_ORDER,
                priority=priority, icon=icon, extra_data=extra_data,
                send_push=send_push
            )
        return None

    @staticmethod
    def send_to_delivery_person(user_id, message, title=None, link=None, type_=None, priority=None, icon=None, extra_data=None, send_push=True):
        if user_id:
            return NotificationService.send_to_user(
                user_id, message, title=title, link=link,
                type_=type_ or NotificationService.TYPE_DELIVERY,
                priority=priority, icon=icon, extra_data=extra_data,
                send_push=send_push
            )
        return None

    @staticmethod
    def send_to_admins(message, title=None, link=None, type_=None, priority=None, icon=None, extra_data=None, exclude_user_id=None, send_push=True):
        admins = models.User.query.filter_by(role='admin', is_active=True).all()
        notifs = []
        for admin in admins:
            if exclude_user_id and admin.id == exclude_user_id:
                continue
            n = NotificationService.send_to_user(
                admin.id, message, title=title, link=link,
                type_=type_ or NotificationService.TYPE_ALERT,
                priority=priority, icon=icon, extra_data=extra_data,
                send_push=send_push
            )
            if n:
                notifs.append(n)
        return notifs

    @staticmethod
    def send_to_role(role, message, title=None, link=None, type_=None, priority=None, icon=None, extra_data=None, send_push=True):
        users = models.User.query.filter_by(role=role, is_active=True).all()
        notifs = []
        for user in users:
            n = NotificationService.send_to_user(
                user.id, message, title=title, link=link,
                type_=type_ or NotificationService.TYPE_INFO,
                priority=priority, icon=icon, extra_data=extra_data,
                send_push=send_push
            )
            if n:
                notifs.append(n)
        return notifs

    @staticmethod
    def send_to_all_users(message, title=None, link=None, type_=None, priority=None, icon=None, extra_data=None, send_push=True):
        users = models.User.query.filter_by(is_active=True).all()
        notifs = []
        for user in users:
            n = NotificationService.send_to_user(
                user.id, message, title=title, link=link,
                type_=type_ or NotificationService.TYPE_INFO,
                priority=priority, icon=icon, extra_data=extra_data,
                send_push=send_push
            )
            if n:
                notifs.append(n)
        return notifs

    @staticmethod
    def mark_as_read(notification_id, user_id=None):
        notif = models.Notification.query.get(notification_id)
        if not notif:
            return False
        if user_id and notif.user_id != user_id:
            return False
        notif.is_read = True
        return True

    @staticmethod
    def mark_all_as_read(user_id):
        models.Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
        db.session.commit()
        return True

    @staticmethod
    def delete(notification_id, user_id=None):
        notif = models.Notification.query.get(notification_id)
        if not notif:
            return False
        if user_id and notif.user_id != user_id:
            return False
        db.session.delete(notif)
        return True

    @staticmethod
    def delete_all_read(user_id):
        models.Notification.query.filter_by(user_id=user_id, is_read=True).delete()
        db.session.commit()
        return True

    @staticmethod
    def get_unread_count(user_id):
        return models.Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def get_user_notifications(user_id, limit=20, offset=0):
        query = models.Notification.query.filter(models.Notification.user_id == user_id) \
            .order_by(models.Notification.created_at.desc())
        return query.offset(offset).limit(limit).all()

    @staticmethod
    def commit():
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
