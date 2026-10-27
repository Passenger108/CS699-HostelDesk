from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm.attributes import set_committed_value

from app.cleaning.models import CleaningRequest, Priority, RequestStatus
from app.cleaning.service import (
    approve_request,
    availability_label,
    board_group,
    change_request,
    operations_board,
    submit_request,
)
from app.cleaning.workflow import transition
from app.common.audit import AuditLog
from app.common.errors import ApiError
from app.common.models import as_utc
from app.common.time import HOSTEL_TZ
from app.credits.service import grant_weekly_credit
from app.extensions import db
from app.hostel_structure.service import find_room
from app.users.models import Role, StudentProfile

NOW = datetime(2026, 10, 21, 10, 0, tzinfo=HOSTEL_TZ)
URL = "/api/v1/cleaning/requests"
S = RequestStatus


@pytest.fixture
def boss(make_user):
    return make_user(login_id="sup", role=Role.SUPERVISOR, name="Sup")


@pytest.fixture
def submitted(resident):
    grant_weekly_credit(resident, NOW)
    db.session.commit()
    return submit_request(resident, availability_mode="ANY_TIME_TODAY", now=NOW)[0]


@pytest.fixture
def urgent(make_user, hostel):
    student = make_user(login_id="upstairs", phone="+91 90000 22222")
    student.student_profile = StudentProfile(roll_number="24B0201", room=find_room("A201"))
    return submit_request(
        student,
        availability_mode="AVAILABLE_NOW",
        priority="URGENT",
        urgent_reason="Leak",
        now=NOW,
    )[0]


def error_of(fn, *args, **kwargs):
    with pytest.raises(ApiError) as err:
        fn(*args, **kwargs)
    return err.value


def change(request, boss, **fields):
    fields.setdefault("lock_version", request.lock_version)
    fields.setdefault("reason", "Called the student")
    return change_request(request, boss, now=NOW, **fields)


def test_approve_moves_to_awaiting_assignment_once(submitted, boss):
    approve_request(submitted, boss)
    approve_request(submitted, boss)

    assert submitted.status == S.AWAITING_ASSIGNMENT
    assert [e.event_type for e in submitted.events] == ["SUBMITTED", "APPROVED"]
    audit = db.session.scalar(db.select(AuditLog).filter_by(action="REQUEST_APPROVED"))
    assert (audit.before_json, audit.after_json) == (
        {"status": "SUBMITTED"},
        {"status": "AWAITING_ASSIGNMENT"},
    )


@pytest.mark.parametrize("state", [S.AWAITING_STUDENT_RESCHEDULE, S.CANCELLED_BY_STUDENT])
def test_approve_needs_submitted(submitted, boss, state):
    submitted.status = state
    db.session.commit()
    assert error_of(approve_request, submitted, boss).code == "CANNOT_APPROVE"


def test_approve_race_returns_the_approved_request(submitted, boss, make_user):
    other = make_user(login_id="sup2", role=Role.SUPERVISOR)
    version = submitted.lock_version
    transition(submitted, S.AWAITING_ASSIGNMENT, actor=other, event_type="APPROVED")
    db.session.commit()
    set_committed_value(submitted, "status", S.SUBMITTED)
    set_committed_value(submitted, "lock_version", version)
    set_committed_value(submitted, "events", submitted.events[:1])

    assert approve_request(submitted, boss).status == S.AWAITING_ASSIGNMENT
    assert (
        db.session.scalar(db.select(db.func.count()).filter(AuditLog.action == "REQUEST_APPROVED"))
        == 0
    )


def test_change_priority_and_window(submitted, boss):
    change(
        submitted,
        boss,
        priority="EMERGENCY",
        availability_mode="TIME_WINDOW",
        window_start="15:00",
        window_end="16:00",
    )

    assert submitted.priority == Priority.EMERGENCY
    assert as_utc(submitted.window_start) == datetime(2026, 10, 21, 15, 0, tzinfo=HOSTEL_TZ)
    event = submitted.events[-1]
    assert (event.event_type, event.payload_json["reason"]) == (
        "DETAILS_CHANGED",
        "Called the student",
    )
    assert event.payload_json["before"]["priority"] == "NORMAL"
    audit = db.session.scalar(db.select(AuditLog).filter_by(action="REQUEST_DETAILS_CHANGED"))
    assert (audit.reason, audit.after_json["availability_mode"]) == (
        "Called the student",
        "TIME_WINDOW",
    )


def test_repeating_a_change_is_a_no_op(submitted, boss):
    change(submitted, boss, priority="URGENT")
    change(submitted, boss, priority="URGENT", lock_version=0)
    assert [e.event_type for e in submitted.events].count("DETAILS_CHANGED") == 1


@pytest.mark.parametrize(
    "fields, code",
    [
        ({"reason": "  "}, "REASON_REQUIRED"),
        ({"lock_version": "1", "priority": "URGENT"}, "INVALID_FIELD"),
        ({"lock_version": True, "priority": "URGENT"}, "INVALID_FIELD"),
        ({}, "NO_CHANGE"),
        ({"priority": "LOW"}, "INVALID_PRIORITY"),
        ({"window_start": "15:00"}, "INVALID_AVAILABILITY"),
        ({"priority": "URGENT", "lock_version": 99}, "STALE_REQUEST"),
    ],
)
def test_change_rejects_bad_input(submitted, boss, fields, code):
    assert error_of(change, submitted, boss, **fields).code == code
    assert submitted.priority == Priority.NORMAL


def test_change_needs_a_changeable_state(submitted, boss):
    submitted.status = S.OFFERED
    db.session.commit()
    assert error_of(change, submitted, boss, priority="URGENT").code == "CANNOT_CHANGE"


def test_urgent_without_credit_cannot_become_normal(urgent, boss):
    assert error_of(change, urgent, boss, priority="NORMAL").code == "NO_CREDIT"
    assert change(urgent, boss, priority="EMERGENCY").priority == Priority.EMERGENCY


@pytest.mark.parametrize(
    "status, priority, group",
    [
        (S.SUBMITTED, Priority.URGENT, "urgent"),
        (S.AWAITING_REASSIGNMENT, Priority.EMERGENCY, "urgent"),
        (S.SUBMITTED, Priority.NORMAL, "new"),
        (S.AWAITING_STUDENT_RESCHEDULE, Priority.NORMAL, "awaiting_assignment"),
        (S.OFFERED, Priority.URGENT, "offered"),
        (S.EN_ROUTE, Priority.NORMAL, "active"),
        (S.SUPERVISOR_INTERVENTION, Priority.NORMAL, "disputed"),
        (S.EXPIRED, Priority.NORMAL, "failed"),
        (S.CLOSED_SUCCESSFUL, Priority.NORMAL, None),
    ],
)
def test_board_group(status, priority, group):
    request = CleaningRequest(status=status, priority=priority)
    assert board_group(request, NOW) == group


@pytest.mark.parametrize("minutes, group", [(19, "active"), (20, "delayed")])
def test_delayed_after_original_eta(minutes, group):
    request = CleaningRequest(
        status=S.ACCEPTED_QUEUED,
        priority=Priority.NORMAL,
        accepted_at=NOW - timedelta(minutes=minutes),
        original_eta_minutes=20,
    )
    assert board_group(request, NOW) == group


def test_board_lists_groups_in_order(submitted, urgent, boss):
    approve_request(submitted, boss)
    board = operations_board(NOW)
    groups = {group["key"]: [r["id"] for r in group["requests"]] for group in board["groups"]}
    assert list(groups) == [
        "urgent",
        "new",
        "awaiting_assignment",
        "offered",
        "active",
        "delayed",
        "disputed",
        "failed",
    ]
    assert groups["awaiting_assignment"] == [submitted.id]
    assert groups["urgent"] == [urgent.id]
    assert board["groups"][0]["label"] == "Urgent and emergency"


def test_supervisor_api_flow(submitted, boss, auth_get, client, login):
    token = login("sup").get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    seen = client.get(f"{URL}/{submitted.id}", headers=headers).get_json()["request"]
    assert seen["actions"] == ["approve", "change"]

    res = client.patch(
        f"{URL}/{submitted.id}",
        json={"priority": "URGENT", "reason": "Exam week", "lock_version": seen["lock_version"]},
        headers=headers,
    )
    assert res.get_json()["request"]["priority"] == "URGENT"
    res = client.post(f"{URL}/{submitted.id}/approve", headers=headers)
    assert res.get_json()["request"]["actions"] == ["change", "offer"]

    board = client.get("/api/v1/cleaning/board", headers=headers).get_json()
    assert board["groups"][0]["requests"][0]["id"] == submitted.id
    student = auth_get(f"{URL}/{submitted.id}", login_id="resident").get_json()["request"]
    assert [e["label"] for e in student["timeline"]][1:] == [
        "Priority or time changed by the supervisor",
        "Approved by the supervisor",
    ]


@pytest.mark.parametrize(
    "method, path",
    [("post", f"{URL}/1/approve"), ("patch", f"{URL}/1"), ("get", "/api/v1/cleaning/board")],
)
def test_only_supervisors_can_use_supervisor_endpoints(submitted, client, login, method, path):
    token = login("resident").get_json()["access_token"]
    res = getattr(client, method)(path, json={}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_change_body_must_be_text(submitted, boss, client, login):
    token = login("sup").get_json()["access_token"]
    res = client.patch(
        f"{URL}/{submitted.id}", json={"reason": 5}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.get_json()["error"]["code"] == "INVALID_FIELD"


@pytest.mark.parametrize("closed_hours_ago, shown", [(9, True), (11, False)])
def test_failed_requests_show_for_today_only(submitted, closed_hours_ago, shown):
    transition(submitted, S.EXPIRED)
    submitted.closed_at = (NOW - timedelta(hours=closed_hours_ago)).astimezone(timezone.utc)
    db.session.commit()
    failed = operations_board(NOW)["groups"][-1]["requests"]
    assert [r["id"] for r in failed] == ([submitted.id] if shown else [])


def test_seed_demo_requests_is_repeatable(app):
    runner = app.test_cli_runner()
    assert "seed-demo first" in runner.invoke(args=["seed-demo-requests"]).output
    runner.invoke(args=["seed-demo"])
    first = runner.invoke(args=["seed-demo-requests"]).output
    again = runner.invoke(args=["seed-demo-requests"]).output
    assert (first.count("created "), again.count("exists ")) == (4, 4)
    assert first.count("AWAITING_ASSIGNMENT") == 1
    assert (first.count("placed "), first.count("offered "), again.count("offered ")) == (2, 1, 0)
    assert "accepted request 4 by demo.worker2, ETA 15 min" in first


@pytest.mark.parametrize(
    "mode, start, end, now_hours, label",
    [
        ("TIME_WINDOW", "21:00", "22:30", 0, "Today, 9:00 pm to 10:30 pm"),
        ("TIME_WINDOW", "12:00", "13:05", 24, "21 Oct, 12:00 pm to 1:05 pm"),
        ("AVAILABLE_NOW", None, None, 0, "Available now"),
        ("AVAILABLE_NOW", None, None, 24, "Available on 21 Oct"),
        ("ANY_TIME_TODAY", None, None, 0, "Any time today"),
        ("ANY_TIME_TODAY", None, None, 24, "Any time on 21 Oct"),
    ],
)
def test_availability_label(resident, mode, start, end, now_hours, label):
    request = submit_request(
        resident, mode, start, end, priority="URGENT", urgent_reason="x", now=NOW
    )[0]
    assert availability_label(request, NOW + timedelta(hours=now_hours)) == label


def test_stale_change_names_who_changed_it(submitted, boss):
    change(submitted, boss, priority="URGENT")
    err = error_of(change, submitted, boss, priority="EMERGENCY", lock_version=1)
    assert err.message == "This request was updated by Sup. Please refresh."
