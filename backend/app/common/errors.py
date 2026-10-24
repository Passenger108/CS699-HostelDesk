from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


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
}


def fail(key: str, field: str | None = None, /, **values) -> ApiError:
    status, message, *code = ERRORS[key]
    return ApiError(status, code[0] if code else key, message.format(**values), field)


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
