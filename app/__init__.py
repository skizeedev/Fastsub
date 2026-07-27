from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()
oauth = OAuth()

login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)

    app.config.from_object("config.Config")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    oauth.init_app(app)

    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=(
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        client_kwargs={
             "scope": "openid email profile"
        }
    )

    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)

    from app.models.user import User
    from app.models.transaction import Transaction
    from app.models.wallet_transaction import WalletTransaction
    from app.models.data_plan import DataPlan
    from flask_login import current_user
    from app.models.notification import Notification

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.webhook import webhook_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(webhook_bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "errors/404.html"
        ),404


    @app.errorhandler(500)
    def internal_server(error):
        db.session.rollback()

        return render_template(
            "errors/500.html"
        ),500

    @app.context_processor
    def inject_notifications():

        if current_user.is_authenticated:

            unread_notifications = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()

            latest_notifications = Notification.query.filter_by(
                user_id=current_user.id
            ).order_by(
                Notification.created_at.desc()
            ).limit(5).all()

        else:

            unread_notifications = 0
            latest_notifications = []

        return dict(
            unread_notifications=unread_notifications,
            latest_notifications=latest_notifications
        )

    return app
