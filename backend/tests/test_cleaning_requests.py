from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm.attributes import set_committed_value

from app.cleaning import service
from app.cleaning.models import (
    AvailabilityMode,
    CleaningRequest,
    CreditReservation,
    Priority,
    RequestStatus,
)
from app.cleaning.service import active_request, cancel_by_student, submit_request
from app.cleaning.workflow import transition
from app.common.audit import AuditLog
from app.common.errors import ApiError
from app.common.models import as_utc
from app.common.time import HOSTEL_TZ
from app.credits.service import balance, grant_goodwill, grant_weekly_credit
from app.extensions import db
from app.users.models import Role

NOW = datetime(2026, 10, 19, 10, 0, tzinfo=HOSTEL_TZ)


def submit(student, now=NOW, **fields):
    fields.setdefault("availability_mode", "ANY_TIME_TODAY")
    return submit_request(student, now=now, **fields)[0]


@pytest.fixture
def credited(resident):
    grant_weekly_credit(resident, NOW)
    db.session.commit()
    return resident


def error_of(fn, *args, **kwargs):
    with pytest.raises(ApiError) as err:
        fn(*args, **kwargs)
    return err.value


def test_submit_reserves_a_credit(credited):
    request = submit(credited, note="  Please mop under the bed  ")

    assert request.status == RequestStatus.SUBMITTED
    assert request.priority == Priority.NORMAL
    assert request.note == "Please mop under the bed"
    assert request.credit_reservation == CreditReservation.RESERVED
    assert request.room_snapshot["number"] == "A102"
    assert request.contact_phone == "+91 90000 11111"
    assert [e.event_type for e in request.events] == ["SUBMITTED"]
    assert as_utc(request.available_until) == datetime(2026, 10, 19, 23, 59, 59, tzinfo=HOSTEL_TZ)
    assert balance(credited.id, NOW)["available"] == 0
    assert balance(credited.id, NOW)["reserved"] == 1
    assert db.session.scalar(db.select(AuditLog).filter_by(action="REQUEST_SUBMITTED"))


def test_second_active_request_is_refused(credited):
    submit(credited)
    grant_weekly_credit(credited, NOW + timedelta(weeks=1))
    err = error_of(submit, credited)
    assert (err.status, err.code) == (409, "ACTIVE_REQUEST_EXISTS")


def test_normal_request_needs_a_credit(resident):
    err = error_of(submit, resident)
    assert (err.status, err.code) == (409, "NO_CREDIT")
    assert active_request(resident) is None


def test_urgent_request_without_credit_reserves_nothing(resident):
    request = submit(resident, priority="URGENT", urgent_reason="Water leak")
    assert request.priority == Priority.URGENT
    assert request.urgent_reason == "Water leak"
    assert request.credit_reservation == CreditReservation.NONE


def test_urgent_request_with_credit_reserves_it(credited):
    request = submit(credited, priority="URGENT", urgent_reason="Spilled food")
    assert request.credit_reservation == CreditReservation.RESERVED


def test_urgent_request_needs_a_reason(credited):
    err = error_of(submit, credited, priority="URGENT", urgent_reason="  ")
    assert err.code == "URGENT_REASON_REQUIRED"


def test_students_cannot_ask_for_emergency(credited):
    assert error_of(submit, credited, priority="EMERGENCY").code == "INVALID_PRIORITY"
    assert error_of(submit, credited, priority="LOW").code == "INVALID_PRIORITY"


def test_note_is_limited_to_500_characters(credited):
    assert error_of(submit, credited, note="x" * 501).code == "NOTE_TOO_LONG"
    assert submit(credited, note="x" * 500).note == "x" * 500


def test_time_window_is_stored(credited):
    request = submit(
        credited, availability_mode="TIME_WINDOW", window_start="14:00", window_end="15:30"
    )
    assert request.availability_mode == AvailabilityMode.TIME_WINDOW
    assert as_utc(request.window_start) == datetime(2026, 10, 19, 14, 0, tzinfo=HOSTEL_TZ)
    assert as_utc(request.window_end) == datetime(2026, 10, 19, 15, 30, tzinfo=HOSTEL_TZ)
    assert as_utc(request.available_until) == as_utc(request.window_end)


@pytest.mark.parametrize(
    "start, end",
    [
        ("15:00", "14:00"),
        ("14:00", "14:00"),
        ("09:00", "11:00"),
        ("25:00", "26:00"),
        ("2pm", "3pm"),
        (None, "15:00"),
    ],
)
def test_invalid_time_windows_are_refused(credited, start, end):
    err = error_of(
        submit, credited, availability_mode="TIME_WINDOW", window_start=start, window_end=end
    )
    assert (err.status, err.code) == (400, "INVALID_AVAILABILITY")
    assert balance(credited.id, NOW)["available"] == 1


def test_window_may_start_this_minute(credited):
    now = NOW + timedelta(seconds=40)
    request = submit(
        credited, now=now, availability_mode="TIME_WINDOW", window_start="10:00", window_end="10:30"
    )
    assert request.status == RequestStatus.SUBMITTED


def test_unknown_availability_is_refused(credited):
    assert error_of(submit, credited, availability_mode="LATER").code == "INVALID_AVAILABILITY"
    assert error_of(submit, credited, availability_mode=None).code == "INVALID_AVAILABILITY"


def test_student_needs_room_and_phone(make_user, hostel, resident):
    no_room = make_user(login_id="noroom", role=Role.STUDENT, phone="+91 1")
    assert error_of(submit, no_room).code == "PROFILE_INCOMPLETE"
    resident.phone = None
    db.session.commit()
    assert error_of(submit, resident).code == "PHONE_REQUIRED"


def test_same_client_key_returns_the_same_request(credited):
    first, created = submit_request(
        credited, availability_mode="AVAILABLE_NOW", client_key="abc", now=NOW
    )
    again, created_again = submit_request(
        credited, availability_mode="AVAILABLE_NOW", client_key="abc", now=NOW
    )
    assert created and not created_again
    assert again.id == first.id
    assert balance(credited.id, NOW)["reserved"] == 1


def test_cancel_releases_the_credit(credited):
    request = submit(credited)
    cancel_by_student(request, credited)

    assert request.status == RequestStatus.CANCELLED_BY_STUDENT
    assert request.credit_reservation == CreditReservation.RELEASED
    assert request.closed_at is not None
    assert active_request(credited) is None
    assert balance(credited.id, NOW)["available"] == 1
    assert balance(credited.id, NOW)["reserved"] == 0
    assert [e.event_type for e in request.events] == ["SUBMITTED", "CANCELLED_BY_STUDENT"]
    assert db.session.scalar(db.select(AuditLog).filter_by(action="REQUEST_CANCELLED"))


def test_cancel_twice_gives_the_same_result(credited):
    request = submit(credited)
    cancel_by_student(request, credited)
    cancel_by_student(request, credited)
    assert len(request.events) == 2
    assert balance(credited.id, NOW)["available"] == 1


def test_cancel_urgent_request_without_credit(resident):
    request = submit(resident, priority="URGENT", urgent_reason="Leak")
    cancel_by_student(request, resident)
    assert request.credit_reservation == CreditReservation.NONE


def test_new_request_allowed_after_cancel(credited):
    cancel_by_student(submit(credited), credited)
    assert submit(credited).status == RequestStatus.SUBMITTED


def test_cannot_cancel_after_cleaning_started(credited):
    request = submit(credited)
    request.status = RequestStatus.CLEANING_IN_PROGRESS
    db.session.commit()
    err = error_of(cancel_by_student, request, credited)
    assert (err.status, err.code) == (409, "CANNOT_CANCEL")
    assert balance(credited.id, NOW)["reserved"] == 1


def test_cannot_cancel_someone_elses_request(credited, make_user):
    request = submit(credited)
    other = make_user(login_id="other", role=Role.STUDENT)
    assert error_of(cancel_by_student, request, other).status == 404


def test_expired_request_frees_the_student(credited):
    request = submit(credited)
    transition(request, RequestStatus.EXPIRED)
    db.session.commit()
    assert active_request(credited) is None


def test_urgent_request_never_spends_goodwill(resident, make_user):
    supervisor = make_user(login_id="sup", role=Role.SUPERVISOR)
    grant_goodwill(resident, supervisor, "Valid complaint", now=NOW)
    request = submit(resident, priority="URGENT", urgent_reason="Leak")
    assert request.credit_reservation == CreditReservation.NONE
    assert balance(resident.id, NOW)["goodwill_available"] == 1


def test_normal_request_uses_goodwill(resident, make_user):
    supervisor = make_user(login_id="sup", role=Role.SUPERVISOR)
    grant_goodwill(resident, supervisor, "Valid complaint", now=NOW)
    request = submit(resident)
    assert request.credit_reservation == CreditReservation.RESERVED
    assert balance(resident.id, NOW)["goodwill_available"] == 0


def test_long_client_key_is_refused(credited):
    err = error_of(submit, credited, client_key="k" * 65)
    assert (err.status, err.code, err.field) == (400, "INVALID_FIELD", "client_key")


def test_lost_race_with_the_same_key_returns_the_first_request(credited, monkeypatch):
    first, _ = submit_request(credited, availability_mode="ANY_TIME_TODAY", client_key="k", now=NOW)
    grant_weekly_credit(credited, NOW + timedelta(weeks=1))
    monkeypatch.setattr(service, "_earlier_submit", _miss_once(service._earlier_submit))
    monkeypatch.setattr(service, "active_request", lambda student: None)
    again, created = submit_request(
        credited, availability_mode="ANY_TIME_TODAY", client_key="k", now=NOW
    )
    assert (again.id, created) == (first.id, False)


def _miss_once(real):
    calls = []

    def fake(student, key):
        calls.append(key)
        return None if len(calls) == 1 else real(student, key)

    return fake


def test_lost_race_without_a_key_is_a_409(credited, monkeypatch):
    submit(credited)
    grant_weekly_credit(credited, NOW + timedelta(weeks=1))
    monkeypatch.setattr(service, "active_request", lambda student: None)
    err = error_of(submit, credited)
    assert (err.status, err.code) == (409, "ACTIVE_REQUEST_EXISTS")


def _changed_by_someone_else(request, **values):
    seen = {"status": request.status, "lock_version": request.lock_version}
    db.session.execute(
        db.update(CleaningRequest)
        .where(CleaningRequest.id == request.id)
        .values(lock_version=CleaningRequest.lock_version + 1, **values)
    )
    db.session.commit()
    for key, value in seen.items():
        set_committed_value(request, key, value)


def test_cancel_that_loses_a_race_to_another_cancel_still_succeeds(credited):
    request = submit(credited)
    _changed_by_someone_else(
        request, status=RequestStatus.CANCELLED_BY_STUDENT, active_student_id=None
    )
    result = cancel_by_student(request, credited)
    assert result.status == RequestStatus.CANCELLED_BY_STUDENT


def test_cancel_that_loses_a_race_to_another_change_is_a_409(credited):
    request = submit(credited)
    _changed_by_someone_else(request)
    err = error_of(cancel_by_student, request, credited)
    assert (err.status, err.code) == (409, "STALE_REQUEST")
    assert balance(credited.id, NOW)["reserved"] == 1


def test_request_in_the_last_second_of_the_day_is_refused(credited):
    late = datetime(2026, 10, 19, 23, 59, 59, 500000, tzinfo=HOSTEL_TZ)
    err = error_of(submit, credited, now=late)
    assert (err.code, err.field) == ("INVALID_AVAILABILITY", "availability_mode")


def test_errors_name_the_field(credited):
    assert error_of(submit, credited, note="x" * 501).field == "note"
    assert error_of(submit, credited, priority="URGENT").field == "urgent_reason"
    window = {"availability_mode": "TIME_WINDOW", "window_start": "15:00", "window_end": "14:00"}
    assert error_of(submit, credited, **window).field == "window_end"
