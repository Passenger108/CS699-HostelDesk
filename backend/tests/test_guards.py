from flask import jsonify
from werkzeug.exceptions import TooManyRequests

from app.auth.guards import roles_required
from app.common.audit import AuditLog
from app.extensions import db
from app.users.models import Role


def test_roles_required_enforced_on_backend(app, make_user, login):
    @app.get("/api/v1/_test/supervisor-only")
    @roles_required(Role.SUPERVISOR, Role.SUPER_ADMIN)
    def supervisor_only():
        return jsonify({"ok": True})

    client = app.test_client()
    make_user(login_id="stu", role=Role.STUDENT)
    make_user(login_id="sup", role=Role.SUPERVISOR)

    stu = login("stu").get_json()["access_token"]
    sup = login("sup").get_json()["access_token"]
    url = "/api/v1/_test/supervisor-only"
    assert client.get(url, headers={"Authorization": f"Bearer {stu}"}).status_code == 403
    assert client.get(url, headers={"Authorization": f"Bearer {sup}"}).status_code == 200


def test_forbidden_attempts_are_audited(app, make_user, login):
    @app.get("/api/v1/_test/admin-only")
    @roles_required(Role.SUPER_ADMIN)
    def admin_only():
        return jsonify({"ok": True})

    student = make_user(login_id="stu", role=Role.STUDENT)
    token = login("stu").get_json()["access_token"]
    res = app.test_client().get(
        "/api/v1/_test/admin-only", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403
    entry = db.session.scalar(db.select(AuditLog).filter_by(action="FORBIDDEN"))
    assert entry.actor_id == student.id
    assert entry.entity_id == "/api/v1/_test/admin-only"
    assert entry.after_json == {"method": "GET", "role": "STUDENT"}


def test_too_many_requests_has_a_friendly_message(app):
    @app.get("/api/v1/_test/busy")
    def busy():
        raise TooManyRequests("20 per 1 minute")

    res = app.test_client().get("/api/v1/_test/busy")
    assert res.status_code == 429
    assert res.get_json()["error"] == {
        "code": "TOO_MANY_REQUESTS",
        "message": "Too many attempts. Please wait a minute and try again.",
    }
