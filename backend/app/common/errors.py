from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

TEXT_LIMIT = 500


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field


ERRORS = {
    "BAD_TIME": (400, "{label} must be a time like 14:30.", "INVALID_AVAILABILITY"),
    "BAD_MODE": (
        400,
        "Choose when you are available: now, a time window or any time today.",
        "INVALID_AVAILABILITY",
    ),
    "DAY_OVER": (
        400,
        "Today is over. Please send the request again after midnight.",
        "INVALID_AVAILABILITY",
    ),
    "WINDOW_ORDER": (400, "The start time must be before the end time.", "INVALID_AVAILABILITY"),
    "WINDOW_PAST": (400, "The time window cannot start in the past.", "INVALID_AVAILABILITY"),
    "KEY_TOO_LONG": (400, "client_key can be at most {limit} characters.", "INVALID_FIELD"),
    "BAD_LOCK_VERSION": (400, "lock_version must be a whole number.", "INVALID_FIELD"),
    "BAD_STUDENT_PRIORITY": (400, "Priority must be normal or urgent.", "INVALID_PRIORITY"),
    "EMERGENCY_FOR_STAFF": (
        400,
        "Only a supervisor can mark a request as an emergency.",
        "INVALID_PRIORITY",
    ),
    "BAD_PRIORITY": (400, "Priority must be normal, urgent or emergency.", "INVALID_PRIORITY"),
    "URGENT_REASON_REQUIRED": (400, "Tell us why this request is urgent."),
    "CHANGE_REASON": (400, "Give a reason for the change.", "REASON_REQUIRED"),
    "SETTING_REASON": (400, "A reason is required to change a setting.", "REASON_REQUIRED"),
    "GOODWILL_REASON": (400, "A reason is required for a goodwill credit.", "REASON_REQUIRED"),
    "NO_CHANGE": (400, "Choose a new priority or time."),
    "UNKNOWN_FILTER": (400, "Unknown {label}: {value}.", "INVALID_FILTER"),
    "NOT_WHOLE": (400, "{label} must be a whole number.", "INVALID_FILTER"),
    "OUT_OF_RANGE": (400, "{label} must be between {low} and {high}.", "INVALID_FILTER"),
    "UNKNOWN_SETTING": (400, "There is no setting called {key}."),
    "NOT_A_STUDENT": (400, "Goodwill credits can only be given to students."),
    "HOSTEL_NOT_FOUND": (404, "The hostel structure has not been set up yet."),
    "REQUEST_NOT_FOUND": (404, "This request does not exist."),
    "NOTIFICATION_NOT_FOUND": (404, "This notification does not exist."),
    "PROFILE_INCOMPLETE": (409, "Your profile has no room yet. Please contact the hostel office."),
    "PHONE_REQUIRED": (409, "Your profile has no phone number. Please contact the hostel office."),
    "ACTIVE_REQUEST_EXISTS": (409, "You already have an active cleaning request."),
    "NO_CREDIT": (409, "You have no cleaning credit available."),
    "NORMAL_NEEDS_CREDIT": (
        409,
        "This request has no credit reserved, so it must stay urgent or emergency.",
        "NO_CREDIT",
    ),
    "ALREADY_RESERVED": (409, "A credit is already reserved for this request."),
    "NO_RESERVATION": (409, "No credit is reserved for this request."),
    "CANNOT_CANCEL": (409, "This request can no longer be cancelled."),
    "CANNOT_APPROVE": (409, "This request is not waiting for approval."),
    "CANNOT_CHANGE": (
        409,
        "Priority and time can change only before the request is offered to a worker.",
    ),
    "ILLEGAL_TRANSITION": (409, "This request cannot move from {old} to {new}."),
    "STALE_REQUEST": (409, "This request was updated by {who}. Please refresh."),
    "BAD_LOCATION": (400, "Choose a floor and wing from the list.", "INVALID_LOCATION"),
    "LOCATION_REASON": (400, "Give a reason for correcting the location.", "REASON_REQUIRED"),
    "WORKER_NOT_FOUND": (404, "This worker does not exist."),
    "WORKER_OFF_DUTY": (409, "This worker is off duty and cannot get offers."),
    "CANNOT_OFFER": (409, "Only an approved request that is waiting for a worker can be offered."),
    "OFFER_NOT_FOUND": (404, "This offer does not exist."),
    "OFFER_CLOSED": (409, "This offer is no longer open."),
    "OFFER_EXPIRED": (409, "The time to answer this offer has run out."),
    "BAD_ETA": (400, "Choose an arrival time from 5 to 120 minutes, in steps of 5.", "INVALID_ETA"),
    "DECLINE_REASON": (400, "Give a reason for declining.", "REASON_REQUIRED"),
    "CANCEL_REASON": (400, "Give a reason for cancelling.", "REASON_REQUIRED"),
    "REASSIGN_REASON": (400, "Give a reason for taking the task back.", "REASON_REQUIRED"),
    "CANNOT_REASSIGN": (409, "Only an offered or accepted request can be taken back."),
    "BAD_QUEUE": (400, "order must be a list of request ids.", "INVALID_FIELD"),
    "QUEUE_CHANGED": (409, "The task list changed. Please refresh and try again."),
    "ALREADY_OFF_DUTY": (409, "You are already off duty."),
    "OFF_DUTY_ON_SITE": (409, "Finish your current task before going off duty."),
    "NO_OFF_DUTY_REQUEST": (409, "This worker has not asked to go off duty."),
}


def fail(key: str, field: str | None = None, /, **values) -> ApiError:
    status, message, *code = ERRORS[key]
    return ApiError(status, code[0] if code else key, message.format(**values), field)


def clean_text(value: str | None, field: str, label: str) -> str | None:
    value = (value or "").strip()
    if len(value) > TEXT_LIMIT:
        raise ApiError(
            400,
            f"{field.upper()}_TOO_LONG",
            f"{label} can be at most {TEXT_LIMIT} characters.",
            field=field,
        )
    return value or None


def error_response(status: int, code: str, message: str, field: str | None = None):
    error = {"code": code, "message": message}
    if field:
        error["field"] = field
    return jsonify({"error": error}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return error_response(err.status, err.code, err.message, err.field)

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        if err.code == 429:
            return error_response(
                429, "TOO_MANY_REQUESTS", "Too many attempts. Please wait a minute and try again."
            )
        code = (err.name or "error").upper().replace(" ", "_")
        return error_response(err.code or 500, code, err.description or err.name)
