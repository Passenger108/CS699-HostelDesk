from flask import Blueprint, jsonify

from app.auth.guards import current_user, login_required

bp = Blueprint("users", __name__)


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": current_user().to_dict()})
