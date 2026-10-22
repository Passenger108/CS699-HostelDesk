from datetime import datetime, timedelta, timezone

import pytest

from app.cleaning.service import cancel_by_student, submit_request
from app.common.errors import ApiError
from app.credits.service import grant_weekly_credit
from app.extensions import db
from app.notifications.models import Notification
from app.notifications.service import (
    list_notifications,
    notification_dict,
    notify,
    set_read,
    unread_count,
)
from app.users.models import AccountStatus, Role

NOW = datetime(2026, 10, 20, 4, 30, tzinfo=timezone.utc)


@pytest.fixture
def credited(resident):
    grant_weekly_credit(resident, NOW)
    db.session.commit()
    return resident


@pytest.fixture
def supervisor(make_user):
    return make_user(login_id="sup", role=Role.SUPERVISOR)


def types_for(user):
    return [n.type for n in list_notifications(user)]


def test_submit_notifies_student_and_supervisors(credited, supervisor, make_user):
    make_user(login_id="sup2", role=Role.SUPERVISOR)
    make_user(login_id="worker", role=Role.WORKER)
    make_user(login_id="admin", role=Role.SUPER_ADMIN)
    request, _ = submit_request(credited, availability_mode="ANY_TIME_TODAY", now=NOW)

    assert types_for(credited) == ["REQUEST_SUBMITTED"]
    rows = db.session.scalars(db.select(Notification).order_by(Notification.id)).all()
    assert sorted(n.type for n in rows) == ["NEW_REQUEST", "NEW_REQUEST", "REQUEST_SUBMITTED"]
    assert {n.payload_json["request_id"] for n in rows} == {request.id}


def test_disabled_supervisors_are_skipped(credited, make_user):
    make_user(login_id="old", role=Role.SUPERVISOR, account_status=AccountStatus.DISABLED)
    submit_request(credited, availability_mode="ANY_TIME_TODAY", now=NOW)
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 1


def test_urgent_request_uses_the_urgent_type(resident, supervisor):
    submit_request(
        resident,
        availability_mode="ANY_TIME_TODAY",
        priority="URGENT",
        urgent_reason="Water leak",
        now=NOW,
    )
    [item] = list_notifications(supervisor)
    assert item.type == "NEW_URGENT_REQUEST"
    assert notification_dict(item)["body"] == "Room A102 asked for urgent cleaning: Water leak"


def test_same_client_key_does_not_notify_twice(credited, supervisor):
    for _ in range(2):
        submit_request(credited, availability_mode="ANY_TIME_TODAY", client_key="k1", now=NOW)
    assert types_for(supervisor) == ["NEW_REQUEST"]
    assert types_for(credited) == ["REQUEST_SUBMITTED"]


def test_refused_submit_notifies_nobody(resident, supervisor):
    with pytest.raises(ApiError):
        submit_request(resident, availability_mode="ANY_TIME_TODAY", now=NOW)
    assert db.session.scalar(db.select(db.func.count(Notification.id))) == 0


def test_cancel_notifies_supervisors_once(credited, supervisor):
    request, _ = submit_request(credited, availability_mode="ANY_TIME_TODAY", now=NOW)
    cancel_by_student(request, credited)
    cancel_by_student(request, credited)
    assert types_for(supervisor) == ["REQUEST_CANCELLED_BY_STUDENT", "NEW_REQUEST"]
    assert types_for(credited) == ["REQUEST_SUBMITTED"]


def test_cancel_notifies_the_assigned_worker(credited, supervisor, make_user):
    worker = make_user(login_id="worker", role=Role.WORKER)
    request, _ = submit_request(credited, availability_mode="ANY_TIME_TODAY", now=NOW)
    request.assigned_worker = worker
    db.session.commit()
    cancel_by_student(request, credited)
    assert types_for(worker) == ["REQUEST_CANCELLED_BY_STUDENT"]


def test_newest_first_and_unread_count(resident):
    first = notify(resident, "REQUEST_SUBMITTED", {"request_id": 1, "room": "A102"})
    first.created_at = NOW
    second = notify(resident, "REQUEST_SUBMITTED", {"request_id": 2, "room": "A102"})
    second.created_at = NOW + timedelta(minutes=1)
    same_time = notify(resident, "REQUEST_SUBMITTED", {"request_id": 3, "room": "A102"})
    same_time.created_at = NOW + timedelta(minutes=1)
    db.session.commit()

    assert [n.id for n in list_notifications(resident)] == [same_time.id, second.id, first.id]
    assert unread_count(resident) == 3
    set_read(second, True)
    assert unread_count(resident) == 2
    assert [n.id for n in list_notifications(resident, unread_only=True)] == [
        same_time.id,
        first.id,
    ]


def test_read_is_idempotent_and_unread_clears_it(resident):
    item = notify(resident, "REQUEST_SUBMITTED", {"request_id": 1, "room": "A102"})
    db.session.commit()
    set_read(item, True, now=NOW)
    set_read(item, True, now=NOW + timedelta(hours=1))
    assert notification_dict(item)["read_at"] == NOW.isoformat()
    set_read(item, False)
    assert item.read_at is None
    assert notification_dict(item)["is_read"] is False


def test_unknown_type_is_refused(resident):
    with pytest.raises(ValueError):
        notify(resident, "SOMETHING", {})


def test_dict_has_title_body_and_request_link(resident):
    item = notify(resident, "REQUEST_SUBMITTED", {"request_id": 7, "room": "A102"})
    db.session.commit()
    data = notification_dict(item)
    assert data["title"] == "Request sent"
    assert data["body"] == (
        "Your cleaning request for room A102 is waiting for supervisor approval."
    )
    assert data["request_id"] == 7
    assert data["is_read"] is False
