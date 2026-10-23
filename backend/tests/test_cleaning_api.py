import pytest

from app.cleaning.models import CleaningRequest, RequestStatus
from app.common.audit import AuditLog
from app.common.time import hostel_now
from app.credits.service import grant_weekly_credit
from app.extensions import db
from app.users.models import Role

URL = "/api/v1/cleaning/requests"


@pytest.fixture
def credited(resident):
    grant_weekly_credit(resident)
    db.session.commit()
    return resident


@pytest.fixture
def post(auth_post):
    def _post(url=URL, json=None, login_id="resident"):
        return auth_post(url, json=json, login_id=login_id)

    return _post


@pytest.fixture
def get(auth_get):
    def _get(url, login_id="resident"):
        return auth_get(url, login_id=login_id)

    return _get


def test_submit_and_read_back(credited, post, get):
    res = post(json={"availability_mode": "AVAILABLE_NOW", "note": "Balcony please"})
    assert res.status_code == 201
    body = res.get_json()["request"]
    assert body["status"] == "SUBMITTED"
    assert body["status_label"] == "Waiting for supervisor approval"
    assert body["is_active"] is True
    assert body["credit_reservation"] == "RESERVED"
    assert body["room"]["number"] == "A102"
    assert body["note"] == "Balcony please"
    assert body["actions"] == ["cancel"]
    assert [e["event_type"] for e in body["timeline"]] == ["SUBMITTED"]
    assert body["timeline"][0]["label"] == "Request submitted"

    detail = get(f"{URL}/{body['id']}").get_json()["request"]
    assert detail["id"] == body["id"]
    active = get(f"{URL}/active").get_json()["request"]
    assert active["id"] == body["id"]

    credits = get("/api/v1/me/credits").get_json()["balance"]
    assert (credits["available"], credits["reserved"]) == (0, 1)


def test_time_window_request(credited, post):
    now = hostel_now()
    if now.hour == 23 and now.minute >= 50:
        pytest.skip("too close to midnight for a window later today")
    start = now.replace(second=0, microsecond=0).strftime("%H:%M")
    res = post(
        json={"availability_mode": "TIME_WINDOW", "window_start": start, "window_end": "23:59"}
    )
    assert res.status_code == 201
    assert res.get_json()["request"]["availability"]["mode"] == "TIME_WINDOW"


def test_invalid_window_is_a_400(credited, post):
    res = post(
        json={"availability_mode": "TIME_WINDOW", "window_start": "15:00", "window_end": "14:00"}
    )
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_AVAILABILITY"


def test_second_request_is_refused(credited, post):
    assert post(json={"availability_mode": "ANY_TIME_TODAY"}).status_code == 201
    res = post(json={"availability_mode": "ANY_TIME_TODAY"})
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "ACTIVE_REQUEST_EXISTS"


def test_no_credit_is_refused_but_urgent_is_allowed(resident, post):
    res = post(json={"availability_mode": "AVAILABLE_NOW"})
    assert res.get_json()["error"]["code"] == "NO_CREDIT"
    res = post(
        json={"availability_mode": "AVAILABLE_NOW", "priority": "URGENT", "urgent_reason": "Leak"}
    )
    assert res.status_code == 201
    assert res.get_json()["request"]["credit_reservation"] == "NONE"


def test_retry_with_same_key_returns_the_same_request(credited, post):
    body = {"availability_mode": "AVAILABLE_NOW", "client_key": "tap-1"}
    first = post(json=body)
    again = post(json=body)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.get_json()["request"]["id"] == again.get_json()["request"]["id"]


def test_body_must_be_a_json_object(credited, post):
    assert post(json=["AVAILABLE_NOW"]).get_json()["error"]["code"] == "INVALID_BODY"
    res = post(json={"availability_mode": "AVAILABLE_NOW", "note": 5})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_FIELD"


def test_cancel_returns_the_credit(credited, post, get):
    request_id = post(json={"availability_mode": "AVAILABLE_NOW"}).get_json()["request"]["id"]
    res = post(f"{URL}/{request_id}/cancel")
    assert res.status_code == 200
    body = res.get_json()["request"]
    assert body["status"] == "CANCELLED_BY_STUDENT"
    assert body["credit_reservation"] == "RELEASED"
    assert body["is_active"] is False
    assert body["actions"] == []
    assert [e["event_type"] for e in body["timeline"]] == ["SUBMITTED", "CANCELLED_BY_STUDENT"]

    assert get(f"{URL}/active").get_json()["request"] is None
    credits = get("/api/v1/me/credits").get_json()["balance"]
    assert (credits["available"], credits["reserved"]) == (1, 0)
    assert post(f"{URL}/{request_id}/cancel").status_code == 200


def test_cannot_cancel_once_cleaning_started(credited, post):
    request_id = post(json={"availability_mode": "AVAILABLE_NOW"}).get_json()["request"]["id"]
    request = db.session.get(CleaningRequest, request_id)
    request.status = RequestStatus.CLEANING_IN_PROGRESS
    db.session.commit()
    res = post(f"{URL}/{request_id}/cancel")
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "CANNOT_CANCEL"


def test_other_students_get_404(credited, post, get, make_user):
    request_id = post(json={"availability_mode": "AVAILABLE_NOW"}).get_json()["request"]["id"]
    make_user(login_id="other", role=Role.STUDENT)
    assert get(f"{URL}/{request_id}", login_id="other").status_code == 404
    assert post(f"{URL}/{request_id}/cancel", login_id="other").status_code == 404
    assert get(f"{URL}/999", login_id="resident").status_code == 404


def test_staff_visibility(credited, post, get, make_user):
    request_id = post(json={"availability_mode": "AVAILABLE_NOW"}).get_json()["request"]["id"]
    make_user(login_id="sup", role=Role.SUPERVISOR)
    make_user(login_id="admin", role=Role.SUPER_ADMIN)
    make_user(login_id="worker", role=Role.WORKER)

    seen = get(f"{URL}/{request_id}", login_id="sup").get_json()["request"]
    assert seen["student"]["id"] == credited.id
    assert seen["actions"] == ["approve", "change"]
    assert get(f"{URL}/{request_id}", login_id="admin").status_code == 200
    assert get(f"{URL}/{request_id}", login_id="worker").status_code == 404


def test_only_students_submit_and_cancel(credited, post, make_user):
    request_id = post(json={"availability_mode": "AVAILABLE_NOW"}).get_json()["request"]["id"]
    for login_id, role in [("sup", Role.SUPERVISOR), ("worker", Role.WORKER)]:
        make_user(login_id=login_id, role=role)
        res = post(json={"availability_mode": "AVAILABLE_NOW"}, login_id=login_id)
        assert res.status_code == 403
        assert post(f"{URL}/{request_id}/cancel", login_id=login_id).status_code == 403


def test_login_required(client):
    assert client.post(URL, json={}).status_code == 401
    assert client.get(f"{URL}/active").status_code == 401
    assert client.get(f"{URL}/1").status_code == 401


def test_errors_say_which_field_is_wrong(credited, post):
    res = post(json={"availability_mode": "AVAILABLE_NOW", "priority": "URGENT"})
    assert res.status_code == 400
    assert res.get_json()["error"]["field"] == "urgent_reason"
    res = post(json={"availability_mode": "SOON"})
    assert res.get_json()["error"]["field"] == "availability_mode"


def test_looking_at_someone_elses_request_is_audited(credited, post, get, make_user):
    request_id = post(json={"availability_mode": "AVAILABLE_NOW"}).get_json()["request"]["id"]
    other = make_user(login_id="other", role=Role.STUDENT)
    assert get(f"{URL}/{request_id}", login_id="other").status_code == 404
    entry = db.session.scalar(db.select(AuditLog).filter_by(action="ACCESS_DENIED"))
    assert (entry.actor_id, entry.entity_id) == (other.id, str(request_id))
    assert get(f"{URL}/999", login_id="other").status_code == 404
    count = db.session.scalar(
        db.select(db.func.count(AuditLog.id)).filter_by(action="ACCESS_DENIED")
    )
    assert count == 1


def test_wrong_role_is_audited(credited, post, make_user):
    make_user(login_id="worker", role=Role.WORKER)
    assert post(json={"availability_mode": "AVAILABLE_NOW"}, login_id="worker").status_code == 403
    assert db.session.scalar(db.select(AuditLog).filter_by(action="FORBIDDEN"))
