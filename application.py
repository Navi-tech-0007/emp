from flask import Flask
from flask_login import LoginManager
import config

# Import blueprints
from routes.auth import auth_bp
from routes.main import main_bp
from routes.registration import registration_bp
from routes.admin import admin_bp
from routes.schedule import schedule_bp
from routes.leave import leave_bp
from routes.api import api_bp
from util import get_user_by_username, User

application = Flask(__name__)
application.config.from_object(config)
application.secret_key = application.config['FLASK_SECRET']

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

# ...any other setup or helper functions...