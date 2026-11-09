from flask import Blueprint, jsonify, request

from app.auth.guards import current_user, login_required, roles_required
from app.cleaning.arrival import (
    accept_wait,
    answer_door,
    arrive,
    mark_unavailable,
    refuse_wait,
    report_problem,
    resolve_intervention,
    set_off,
    start_cleaning,
)
from app.cleaning.delays import flag_delay, reschedule, resolve_delay, update_eta
from app.cleaning.recommendations import recommend
from app.cleaning.schemas import SUPERVISOR_ROLES, operations_board, request_dict
from app.cleaning.service import (
    active_request,
    approve_request,
    cancel_request,
    change_request,
    get_request_for,
    list_requests,
    offer_request,
    reassign_request,
    submit_request,
)
from app.common.errors import ApiError
from app.users.models import Role

bp = Blueprint("cleaning", __name__, url_prefix="/cleaning")

TEXT_FIELDS = (
    "availability_mode",
    "window_start",
    "window_end",
    "priority",
    "note",
    "urgent_reason",
    "client_key",
    "reason",
    "answer",
    "decision",
)
WORKER_STEPS = {
    "en-route": set_off,
    "arrive": arrive,
    "accept-wait": accept_wait,
    "refuse-wait": refuse_wait,
    "start": start_cleaning,
    "student-unavailable": mark_unavailable,
}
STEP_PATH = "/requests/<int:request_id>/<any({}):step>".format(
    ", ".join(f"'{step}'" for step in WORKER_STEPS)
)


def json_body() -> dict:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_BODY", "Send the request details as a JSON object.")
    for field in TEXT_FIELDS:
        value = body.get(field)
        if value is not None and not isinstance(value, str):
            raise ApiError(400, "INVALID_FIELD", f"The field {field} must be text.")
    return body


@bp.post("/requests")
@roles_required(Role.STUDENT)
def create_request():
    body = json_body()
    student = current_user()
    cleaning_request, created = submit_request(
        student,
        availability_mode=body.get("availability_mode"),
        window_start=body.get("window_start"),
        window_end=body.get("window_end"),
        priority=body.get("priority"),
        note=body.get("note"),
        urgent_reason=body.get("urgent_reason"),
        client_key=body.get("client_key") or request.headers.get("Idempotency-Key"),
    )
    return jsonify({"request": request_dict(cleaning_request, student)}), 201 if created else 200


@bp.get("/requests")
@login_required
def all_requests():
    args = request.args
    return jsonify(
        list_requests(
            current_user(),
            status=args.get("status"),
            floor=args.get("floor"),
            priority=args.get("priority"),
            page=args.get("page"),
            per_page=args.get("per_page"),
        )
    )


@bp.get("/requests/active")
@roles_required(Role.STUDENT)
def my_active_request():
    student = current_user()
    cleaning_request = active_request(student)
    return jsonify(
        {"request": request_dict(cleaning_request, student) if cleaning_request else None}
    )


@bp.get("/requests/<int:request_id>")
@login_required
def get_request(request_id: int):
    viewer = current_user()
    return jsonify({"request": request_dict(get_request_for(request_id, viewer), viewer)})


@bp.post("/requests/<int:request_id>/cancel")
@roles_required(Role.STUDENT, *SUPERVISOR_ROLES)
def cancel(request_id: int):
    viewer = current_user()
    reason = json_body().get("reason") if viewer.role in SUPERVISOR_ROLES else None
    cleaning_request = cancel_request(get_request_for(request_id, viewer), viewer, reason)
    return jsonify({"request": request_dict(cleaning_request, viewer)})


@bp.post("/requests/<int:request_id>/approve")
@roles_required(*SUPERVISOR_ROLES)
def approve(request_id: int):
    supervisor = current_user()
    cleaning_request = approve_request(get_request_for(request_id, supervisor), supervisor)
    return jsonify({"request": request_dict(cleaning_request, supervisor)})


@bp.patch("/requests/<int:request_id>")
@roles_required(*SUPERVISOR_ROLES)
def change(request_id: int):
    body = json_body()
    supervisor = current_user()
    fields = ("reason", "priority", "availability_mode", "window_start", "window_end")
    cleaning_request = change_request(
        get_request_for(request_id, supervisor),
        supervisor,
        lock_version=body.get("lock_version"),
        **{field: body.get(field) for field in fields},
    )
    return jsonify({"request": request_dict(cleaning_request, supervisor)})


@bp.get("/requests/<int:request_id>/recommendations")
@roles_required(*SUPERVISOR_ROLES)
def recommendations(request_id: int):
    return jsonify({"recommendations": recommend(get_request_for(request_id, current_user()))})


@bp.post("/requests/<int:request_id>/offers")
@roles_required(*SUPERVISOR_ROLES)
def offer(request_id: int):
    body = json_body()
    supervisor = current_user()
    cleaning_request = offer_request(
        get_request_for(request_id, supervisor),
        supervisor,
        body.get("worker_id"),
        body.get("lock_version"),
    )
    return jsonify({"request": request_dict(cleaning_request, supervisor)}), 201


@bp.post("/requests/<int:request_id>/reassign")
@roles_required(*SUPERVISOR_ROLES)
def reassign(request_id: int):
    body = json_body()
    supervisor = current_user()
    cleaning_request = reassign_request(
        get_request_for(request_id, supervisor),
        supervisor,
        body.get("reason"),
        body.get("lock_version"),
        body.get("worker_id"),
    )
    return jsonify({"request": request_dict(cleaning_request, supervisor)})


@bp.get("/board")
@roles_required(*SUPERVISOR_ROLES)
def board():
    return jsonify(operations_board())


@bp.post(STEP_PATH)
@roles_required(Role.WORKER)
def worker_step(request_id: int, step: str):
    worker = current_user()
    cleaning_request = WORKER_STEPS[step](get_request_for(request_id, worker), worker)
    return jsonify({"request": request_dict(cleaning_request, worker)})


@bp.post("/requests/<int:request_id>/problem")
@roles_required(Role.WORKER)
def problem(request_id: int):
    worker = current_user()
    reason = json_body().get("reason")
    cleaning_request = report_problem(get_request_for(request_id, worker), worker, reason)
    return jsonify({"request": request_dict(cleaning_request, worker)})


@bp.post("/requests/<int:request_id>/arrival-response")
@roles_required(Role.STUDENT)
def arrival_response(request_id: int):
    student = current_user()
    answer = json_body().get("answer")
    cleaning_request = answer_door(get_request_for(request_id, student), student, answer)
    return jsonify({"request": request_dict(cleaning_request, student)})


@bp.post("/requests/<int:request_id>/resolve-intervention")
@roles_required(*SUPERVISOR_ROLES)
def resolve(request_id: int):
    body = json_body()
    supervisor = current_user()
    cleaning_request = resolve_intervention(
        get_request_for(request_id, supervisor),
        supervisor,
        body.get("decision"),
        body.get("reason"),
        body.get("lock_version"),
    )
    return jsonify({"request": request_dict(cleaning_request, supervisor)})


@bp.patch("/requests/<int:request_id>/eta")
@roles_required(Role.WORKER)
def eta(request_id: int):
    worker = current_user()
    minutes = json_body().get("eta_minutes")
    cleaning_request = update_eta(get_request_for(request_id, worker), worker, minutes)
    return jsonify({"request": request_dict(cleaning_request, worker)})


@bp.post("/requests/<int:request_id>/flag-delay")
@roles_required(Role.STUDENT)
def flag(request_id: int):
    student = current_user()
    cleaning_request = flag_delay(get_request_for(request_id, student), student)
    return jsonify({"request": request_dict(cleaning_request, student)})


@bp.post("/requests/<int:request_id>/resolve-delay")
@roles_required(*SUPERVISOR_ROLES)
def resolve_late(request_id: int):
    body = json_body()
    supervisor = current_user()
    cleaning_request = resolve_delay(
        get_request_for(request_id, supervisor),
        supervisor,
        body.get("reason"),
        body.get("lock_version"),
    )
    return jsonify({"request": request_dict(cleaning_request, supervisor)})


@bp.post("/requests/<int:request_id>/reschedule")
@roles_required(Role.STUDENT)
def new_time(request_id: int):
    body = json_body()
    student = current_user()
    cleaning_request = reschedule(
        get_request_for(request_id, student),
        student,
        body.get("availability_mode"),
        body.get("window_start"),
        body.get("window_end"),
    )
    return jsonify({"request": request_dict(cleaning_request, student)})
