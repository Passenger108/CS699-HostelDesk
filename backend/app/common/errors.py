from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return error_response(err.status, err.code, err.message)

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        code = (err.name or "error").upper().replace(" ", "_")
        return error_response(err.code or 500, code, err.description or err.name)
