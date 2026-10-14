from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, verify_jwt_in_request

from app.auth.guards import current_user
from app.auth.service import authenticate
from app.common.errors import ApiError
from app.extensions import limiter

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _login_limit() -> str:
    return current_app.config["LOGIN_RATE_LIMIT"]


@bp.post("/login")
@limiter.limit(_login_limit)
def login():
    data = request.get_json(silent=True) or {}
    login_id = data.get("login_id")
    password = data.get("password")
    if not (isinstance(login_id, str) and isinstance(password, str) and login_id and password):
        raise ApiError(400, "VALIDATION_ERROR", "login_id and password are required.")

    user = authenticate(login_id.strip(), password)
    return jsonify(
        {
            "access_token": create_access_token(identity=user),
            "refresh_token": create_refresh_token(identity=user),
            "user": user.to_dict(),
        }
    )


@bp.post("/refresh")
def refresh():
    verify_jwt_in_request(refresh=True)
    return jsonify({"access_token": create_access_token(identity=current_user())})
