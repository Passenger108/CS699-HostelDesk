from flask import jsonify

from app.auth.guards import roles_required
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
