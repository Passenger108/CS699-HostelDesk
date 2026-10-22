import pytest

from app.common.audit import AuditLog
from app.credits.service import grant_weekly_credit
from app.extensions import db
from app.notifications.service import notify
from app.users.models import Role

URL = "/api/v1/notifications"


@pytest.fixture
def client_for(client, login):
    def _for(login_id):
        token = login(login_id).get_json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        class Caller:
            def get(self, url):
                return client.get(url, headers=headers)

            def patch(self, url):
                return client.patch(url, headers=headers)

            def post(self, url, json=None):
                return client.post(url, json=json, headers=headers)

        return Caller()

    return _for


@pytest.fixture
def setup(resident, make_user):
    grant_weekly_credit(resident)
    db.session.commit()
    make_user(login_id="sup", role=Role.SUPERVISOR)
    return resident


def test_supervisor_sees_new_request(setup, client_for):
    student = client_for("resident")
    res = student.post("/api/v1/cleaning/requests", json={"availability_mode": "AVAILABLE_NOW"})
    request_id = res.get_json()["request"]["id"]

    body = client_for("sup").get(URL).get_json()
    assert body["unread_count"] == 1
    [item] = body["notifications"]
    assert item["type"] == "NEW_REQUEST"
    assert item["title"] == "New cleaning request"
    assert item["body"] == "Room A102 asked for cleaning."
    assert item["request_id"] == request_id
    assert item["is_read"] is False

    mine = student.get(URL).get_json()
    assert [n["type"] for n in mine["notifications"]] == ["REQUEST_SUBMITTED"]


def test_mark_read_and_unread(setup, client_for):
    item = notify(setup, "REQUEST_SUBMITTED", {"request_id": 1, "room": "A102"})
    db.session.commit()
    me = client_for("resident")

    res = me.patch(f"{URL}/{item.id}/read")
    assert res.status_code == 200
    assert res.get_json()["notification"]["is_read"] is True
    assert res.get_json()["unread_count"] == 0
    assert me.patch(f"{URL}/{item.id}/read").status_code == 200
    assert me.get(f"{URL}/unread-count").get_json() == {"unread_count": 0}

    res = me.patch(f"{URL}/{item.id}/unread")
    assert res.get_json()["notification"]["is_read"] is False
    assert me.get(f"{URL}/unread-count").get_json() == {"unread_count": 1}


def test_unread_filter_and_limit(setup, client_for):
    items = [
        notify(setup, "REQUEST_SUBMITTED", {"request_id": i, "room": "A102"}) for i in range(3)
    ]
    db.session.commit()
    me = client_for("resident")
    me.patch(f"{URL}/{items[0].id}/read")

    assert len(me.get(f"{URL}?unread=true").get_json()["notifications"]) == 2
    assert len(me.get(f"{URL}?limit=1").get_json()["notifications"]) == 1
    assert me.get(f"{URL}?limit=0").status_code == 400
    assert me.get(f"{URL}?limit=abc").get_json()["error"]["code"] == "INVALID_FILTER"
    assert me.get(f"{URL}?unread=maybe").status_code == 400


def test_cannot_read_someone_elses_notification(setup, client_for):
    item = notify(setup, "REQUEST_SUBMITTED", {"request_id": 1, "room": "A102"})
    db.session.commit()
    sup = client_for("sup")
    assert sup.patch(f"{URL}/{item.id}/read").status_code == 404
    assert sup.patch(f"{URL}/{item.id}/unread").status_code == 404
    assert sup.patch(f"{URL}/999/read").status_code == 404
    assert item.read_at is None
    assert sup.get(URL).get_json()["notifications"] == []
    denied = db.session.scalars(db.select(AuditLog).filter_by(action="ACCESS_DENIED")).all()
    assert [entry.entity_id for entry in denied] == [str(item.id), str(item.id)]


def test_reading_never_changes_the_request(setup, client_for):
    student = client_for("resident")
    res = student.post("/api/v1/cleaning/requests", json={"availability_mode": "AVAILABLE_NOW"})
    before = res.get_json()["request"]
    sup = client_for("sup")
    item = sup.get(URL).get_json()["notifications"][0]
    sup.patch(f"{URL}/{item['id']}/read")
    after = student.get(f"/api/v1/cleaning/requests/{before['id']}").get_json()["request"]
    assert (after["status"], after["lock_version"]) == (before["status"], before["lock_version"])


def test_login_required(client):
    assert client.get(URL).status_code == 401
    assert client.get(f"{URL}/unread-count").status_code == 401
    assert client.patch(f"{URL}/1/read").status_code == 401
    assert client.patch(f"{URL}/1/unread").status_code == 401
