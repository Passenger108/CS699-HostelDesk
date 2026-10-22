from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field


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
