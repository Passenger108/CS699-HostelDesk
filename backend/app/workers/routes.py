from flask import Blueprint, jsonify

from app.auth.guards import current_user, roles_required
from app.cleaning.routes import json_body
from app.cleaning.service import SUPERVISOR_ROLES
from app.users.models import Role
from app.workers.service import correct_location, list_workers, update_location, worker_dict

bp = Blueprint("workers", __name__, url_prefix="/workers")


@bp.get("")
@roles_required(*SUPERVISOR_ROLES)
def workers():
    return jsonify({"workers": list_workers()})


@bp.patch("/me/location")
@roles_required(Role.WORKER)
def my_location():
    worker = update_location(current_user(), json_body().get("location_id"))
    return jsonify({"worker": worker_dict(worker)})


@bp.patch("/<int:worker_id>/location")
@roles_required(*SUPERVISOR_ROLES)
def correct(worker_id: int):
    body = json_body()
    location_id, reason = body.get("location_id"), body.get("reason")
    worker = correct_location(worker_id, current_user(), location_id, reason)
    return jsonify({"worker": worker_dict(worker)})
