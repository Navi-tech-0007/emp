from flask import Flask
from flask_login import LoginManager, current_user
import config

# Import blueprints
from routes.auth import auth_bp
from routes.main import main_bp, get_unread_notifications
from routes.registration import registration_bp
from routes.admin import admin_bp
from routes.schedule import schedule_bp
from routes.leave import leave_bp
from routes.api import api_bp
from routes.announcements import announcements_bp
from util import get_user_by_username, User

application = Flask(__name__)
application.config.from_object(config)
application.secret_key = application.config['FLASK_SECRET']

import logging
application.logger.setLevel(logging.INFO)

login_manager = LoginManager()
login_manager.init_app(application)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(username):
    user_dict = get_user_by_username(username)
    if user_dict:
        return User(user_dict)
    return None

# Register blueprints
application.register_blueprint(auth_bp)
application.register_blueprint(main_bp)
application.register_blueprint(registration_bp)
application.register_blueprint(admin_bp)
application.register_blueprint(schedule_bp)
application.register_blueprint(leave_bp)
application.register_blueprint(api_bp)
application.register_blueprint(announcements_bp)

@application.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        notifications, unread_count = get_unread_notifications(current_user.username)
        return dict(notifications=notifications, unread_notification_count=unread_count)
    return dict(notifications=[], unread_notification_count=0)

@application.context_processor
def inject_user():
    return dict(user=current_user)