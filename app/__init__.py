import os
from flask import Flask, render_template
from config import Config
from .extensions import db, migrate, login_manager, csrf, limiter, socketio


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app, message_queue=app.config.get("SOCKETIO_MESSAGE_QUEUE"))

    # Models + login loader
    from . import models  # noqa
    from .models import User

    @login_manager.user_loader
    def load_user(uid):
        return User.query.get(int(uid))

    # Blueprints
    from .auth.routes import bp as auth_bp
    from .wallet.routes import bp as wallet_bp
    from .games.routes import bp as games_bp
    from .prediction.routes import bp as prediction_bp
    from .cards.routes import bp as cards_bp
    from .payments.routes import bp as payments_bp
    from .withdraw.routes import bp as withdraw_bp
    from .admin.routes import bp as admin_bp
    from .referrals.routes import bp as referrals_bp
    from .api.routes import bp as api_bp
    from .notifications.routes import bp as notif_bp
    from .security.routes import bp as security_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(wallet_bp, url_prefix="/wallet")
    app.register_blueprint(games_bp, url_prefix="/games")
    app.register_blueprint(prediction_bp, url_prefix="/prediction")
    app.register_blueprint(cards_bp, url_prefix="/cards")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(withdraw_bp, url_prefix="/withdraw")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(referrals_bp, url_prefix="/referrals")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(notif_bp, url_prefix="/notifications")
    app.register_blueprint(security_bp, url_prefix="/security")

    # Webhooks must skip CSRF
    csrf.exempt(payments_bp)
    csrf.exempt(api_bp)

    # Socket handlers
    from . import socket_events  # noqa

    # Public routes
    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.errorhandler(404)
    def nf(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def ie(e):
        return render_template("errors/500.html"), 500

    # Bootstrap admin
    with app.app_context():
        try:
            db.create_all()
            models.bootstrap_admin(app)
        except Exception as exc:  # first run before tables may exist on prod migrations
            app.logger.warning("Bootstrap skipped: %s", exc)

    return app
