from flask import Blueprint, jsonify, request

from app.auth.guards import current_user, roles_required
from app.cleaning.routes import json_body
from app.reports.audit import audit_page
from app.users.models import Role
from app.users.schemas import account_dict
from app.users.service import SHIFTS, create_user, list_users, set_status

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/users")
@roles_required(Role.SUPER_ADMIN)
def users():
    users = [account_dict(user) for user in list_users(request.args.get("role"))]
    return jsonify({"users": users, "shifts": SHIFTS})


@bp.post("/users")
@roles_required(Role.SUPER_ADMIN)
def new_user():
    user = create_user(current_user(), json_body())
    return jsonify({"user": account_dict(user)}), 201


@bp.patch("/users/<int:user_id>")
@roles_required(Role.SUPER_ADMIN)
def change_user(user_id: int):
    user = set_status(current_user(), user_id, json_body().get("account_status"))
    return jsonify({"user": account_dict(user)})


@bp.get("/audit-logs")
@roles_required(Role.SUPER_ADMIN)
def audit_logs():
    return jsonify(audit_page(request.args))
