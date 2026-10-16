from flask import Blueprint, jsonify

from app.auth.guards import current_user, roles_required
from app.credits.service import balance, history
from app.users.models import Role

bp = Blueprint("credits", __name__)


@bp.get("/me/credits")
@roles_required(Role.STUDENT)
def my_credits():
    student = current_user()
    return jsonify({"balance": balance(student.id), "history": history(student.id)})
