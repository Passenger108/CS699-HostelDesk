from flask import Blueprint, jsonify

from app.auth.guards import current_user, login_required
from app.users.service import profile_dict

bp = Blueprint("users", __name__)


@bp.get("/me")
@login_required
def me():
    user = current_user()
    return jsonify({"user": user.to_dict(), "profile": profile_dict(user)})
