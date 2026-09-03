from flask import Blueprint

notifications_bp = Blueprint('notifications', __name__, template_folder='templates')

from . import routes
