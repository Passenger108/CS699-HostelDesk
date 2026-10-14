import os

from dotenv import load_dotenv
from flask import Blueprint, Flask, jsonify

from app.config import CONFIGS
from app.extensions import cors, db, jwt, limiter, migrate


def create_app(config_name: str | None = None) -> Flask:
    load_dotenv()
    config_name = config_name or os.environ.get("HOSTELDESK_CONFIG", "development")

    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name]())

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    jwt.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from app.common.errors import register_error_handlers
    from app.users import models  # noqa: F401

    register_error_handlers(app)
    _register_blueprints(app)

    from app.cli import register_cli

    register_cli(app)
    return app


def _register_blueprints(app: Flask) -> None:
    from app.auth import guards  # noqa: F401
    from app.auth.routes import bp as auth_bp
    from app.users.routes import bp as users_bp

    api = Blueprint("api", __name__, url_prefix="/api/v1")

    @api.get("/health")
    def health():
        return jsonify({"status": "ok"})

    api.register_blueprint(auth_bp)
    api.register_blueprint(users_bp)
    app.register_blueprint(api)
