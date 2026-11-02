from flask import Blueprint, jsonify

from app.auth.guards import current_user, roles_required
from app.cleaning.routes import json_body
from app.cleaning.service import (
    SUPERVISOR_ROLES,
    accept_offer,
    approve_off_duty,
    decline_offer,
    get_offer_for,
    reorder_queue,
    request_dict,
    worker_offers,
)
from app.users.models import Role
from app.workers.service import (
    correct_location,
    get_worker,
    list_workers,
    request_off_duty,
    return_to_duty,
    update_location,
    worker_dict,
)

bp = Blueprint("workers", __name__, url_prefix="/workers")
offers_bp = Blueprint("worker_offers", __name__, url_prefix="/worker/offers")


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


@bp.put("/me/queue")
@roles_required(Role.WORKER)
def my_queue():
    worker = current_user()
    return jsonify({"tasks": reorder_queue(worker, worker, json_body().get("order"))})


@bp.put("/<int:worker_id>/queue")
@roles_required(*SUPERVISOR_ROLES)
def queue(worker_id: int):
    order = json_body().get("order")
    return jsonify({"tasks": reorder_queue(get_worker(worker_id), current_user(), order)})


@bp.post("/me/off-duty-request")
@roles_required(Role.WORKER)
def ask_off_duty():
    return jsonify({"worker": worker_dict(request_off_duty(current_user()))})


@bp.post("/me/on-duty")
@roles_required(Role.WORKER)
def on_duty():
    return jsonify({"worker": worker_dict(return_to_duty(current_user()))})


@bp.post("/<int:worker_id>/off-duty/approve")
@roles_required(*SUPERVISOR_ROLES)
def off_duty(worker_id: int):
    return jsonify({"worker": worker_dict(approve_off_duty(worker_id, current_user()))})


@offers_bp.get("")
@roles_required(Role.WORKER)
def my_offers():
    return jsonify({"offers": worker_offers(current_user())})


@offers_bp.post("/<int:offer_id>/accept")
@roles_required(Role.WORKER)
def accept(offer_id: int):
    worker = current_user()
    eta = json_body().get("eta_minutes")
    request = accept_offer(get_offer_for(offer_id, worker), worker, eta)
    return jsonify({"request": request_dict(request, worker)})


@offers_bp.post("/<int:offer_id>/decline")
@roles_required(Role.WORKER)
def decline(offer_id: int):
    worker = current_user()
    reason = json_body().get("reason")
    request = decline_offer(get_offer_for(offer_id, worker), worker, reason)
    return jsonify({"request": request_dict(request, worker)})
