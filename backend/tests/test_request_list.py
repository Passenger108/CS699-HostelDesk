from datetime import datetime, timedelta, timezone

import pytest

from app.cleaning.models import CleaningRequest
from app.cleaning.service import cancel_by_student, submit_request
from app.credits.service import grant_weekly_credit
from app.extensions import db
from app.hostel_structure.service import find_room
from app.users.models import Role, StudentProfile

URL = "/api/v1/cleaning/requests"
NOW = datetime(2026, 10, 20, 4, 30, tzinfo=timezone.utc)


@pytest.fixture
def students(resident, make_user):
    upstairs = make_user(login_id="upstairs", role=Role.STUDENT, phone="+91 90000 22222")
    upstairs.student_profile = StudentProfile(roll_number="24B0202", room=find_room("A201"))
    db.session.commit()
    for student in (resident, upstairs):
        grant_weekly_credit(student, NOW)
    db.session.commit()
    return resident, upstairs


@pytest.fixture
def history(students):
    resident, upstairs = students
    first, _ = submit_request(resident, availability_mode="ANY_TIME_TODAY", now=NOW)
    cancel_by_student(first, resident)
    second, _ = submit_request(
        resident,
        availability_mode="ANY_TIME_TODAY",
        priority="URGENT",
        urgent_reason="Leak",
        now=NOW,
    )
    third, _ = submit_request(upstairs, availability_mode="ANY_TIME_TODAY", now=NOW)
    for offset, request in enumerate((first, second, third)):
        request.created_at = NOW + timedelta(minutes=offset)
    db.session.commit()
    return first, second, third


def ids(res):
    return [row["id"] for row in res.get_json()["requests"]]


def test_student_sees_only_own_requests_newest_first(history, auth_get):
    first, second, _ = history
    res = auth_get(URL, login_id="resident")
    assert res.status_code == 200
    assert ids(res) == [second.id, first.id]
    body = res.get_json()
    assert (body["page"], body["per_page"], body["total"]) == (1, 20, 2)
    row = body["requests"][0]
    assert row["status_label"] == "Waiting for supervisor approval"
    assert row["room"]["number"] == "A102"
    assert "timeline" not in row and "contact_phone" not in row


def test_supervisor_sees_all_and_can_filter(history, auth_get, make_user):
    first, second, third = history
    make_user(login_id="sup", role=Role.SUPERVISOR)
    assert ids(auth_get(URL, login_id="sup")) == [third.id, second.id, first.id]
    assert ids(auth_get(f"{URL}?status=SUBMITTED", login_id="sup")) == [third.id, second.id]
    assert ids(auth_get(f"{URL}?status=cancelled_by_student", login_id="sup")) == [first.id]
    assert ids(auth_get(f"{URL}?status=SUBMITTED,EXPIRED", login_id="sup")) == [
        third.id,
        second.id,
    ]
    assert ids(auth_get(f"{URL}?priority=URGENT", login_id="sup")) == [second.id]
    assert ids(auth_get(f"{URL}?floor=2", login_id="sup")) == [third.id]
    assert ids(auth_get(f"{URL}?floor=1&priority=NORMAL", login_id="sup")) == [first.id]


def test_super_admin_sees_all(history, auth_get, make_user):
    make_user(login_id="admin", role=Role.SUPER_ADMIN)
    assert auth_get(URL, login_id="admin").get_json()["total"] == 3


def test_worker_sees_only_assigned_requests(history, auth_get, make_user):
    _, second, _ = history
    worker = make_user(login_id="worker", role=Role.WORKER)
    assert ids(auth_get(URL, login_id="worker")) == []
    request = db.session.get(CleaningRequest, second.id)
    request.assigned_worker = worker
    db.session.commit()
    assert ids(auth_get(URL, login_id="worker")) == [second.id]


def test_paging(history, auth_get, make_user):
    first, second, third = history
    make_user(login_id="sup", role=Role.SUPERVISOR)
    page1 = auth_get(f"{URL}?per_page=2", login_id="sup")
    page2 = auth_get(f"{URL}?per_page=2&page=2", login_id="sup")
    assert ids(page1) == [third.id, second.id]
    assert ids(page2) == [first.id]
    assert page2.get_json()["total"] == 3
    assert ids(auth_get(f"{URL}?per_page=2&page=3", login_id="sup")) == []


def test_same_time_rows_keep_a_stable_order(history, auth_get, make_user):
    make_user(login_id="sup", role=Role.SUPERVISOR)
    for request in db.session.scalars(db.select(CleaningRequest)):
        request.created_at = NOW
    db.session.commit()
    expected = sorted(ids(auth_get(URL, login_id="sup")), reverse=True)
    for _ in range(3):
        assert ids(auth_get(URL, login_id="sup")) == expected


@pytest.mark.parametrize(
    "query",
    ["status=DONE", "priority=LOW", "floor=x", "floor=-1", "page=0", "per_page=101", "per_page=a"],
)
def test_bad_filters_are_a_400(history, auth_get, query):
    res = auth_get(f"{URL}?{query}", login_id="resident")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "INVALID_FILTER"


def test_empty_history(resident, auth_get):
    body = auth_get(URL, login_id="resident").get_json()
    assert body == {"requests": [], "page": 1, "per_page": 20, "total": 0}


def test_login_required(client):
    assert client.get(URL).status_code == 401


def test_emergency_priority_filter_is_allowed(history, auth_get, make_user):
    make_user(login_id="sup", role=Role.SUPERVISOR)
    assert ids(auth_get(f"{URL}?priority=EMERGENCY", login_id="sup")) == []
