from datetime import datetime

import pytest

from app.cleaning.models import (
    AvailabilityMode,
    CleaningRequest,
    CreditReservation,
    Priority,
    RequestEvent,
    RequestStatus,
)
from app.cleaning.workflow import (
    ACTIVE_STATES,
    ALLOWED_TRANSITIONS,
    STATUS_LABELS,
    TERMINAL_STATES,
    can_transition,
    transition,
)
from app.common.errors import ApiError
from app.common.time import HOSTEL_TZ
from app.extensions import db

S = RequestStatus


@pytest.fixture
def cleaning_request(resident):
    request = CleaningRequest(
        student=resident,
        active_student_id=resident.id,
        room=resident.student_profile.room,
        room_snapshot={"number": "A102"},
        contact_phone=resident.phone,
        status=S.SUBMITTED,
        priority=Priority.NORMAL,
        availability_mode=AvailabilityMode.ANY_TIME_TODAY,
        available_until=datetime(2026, 10, 17, 23, 59, 59, tzinfo=HOSTEL_TZ),
        credit_reservation=CreditReservation.NONE,
    )
    db.session.add(request)
    db.session.commit()
    return request


def test_every_state_has_a_rule_and_a_label():
    assert set(ALLOWED_TRANSITIONS) == set(S)
    assert set(STATUS_LABELS) == set(S)
    assert ACTIVE_STATES | TERMINAL_STATES == set(S)
    assert not ACTIVE_STATES & TERMINAL_STATES


def test_terminal_states_have_no_way_out():
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == frozenset()


def test_every_active_state_can_move_on():
    for state in ACTIVE_STATES:
        assert ALLOWED_TRANSITIONS[state]


def test_transition_targets_are_known_states():
    for targets in ALLOWED_TRANSITIONS.values():
        assert targets <= set(S)


@pytest.mark.parametrize(
    "old, new, allowed",
    [
        (S.SUBMITTED, S.AWAITING_ASSIGNMENT, True),
        (S.SUBMITTED, S.CANCELLED_BY_STUDENT, True),
        (S.SUBMITTED, S.OFFERED, False),
        (S.SUBMITTED, S.CLOSED_SUCCESSFUL, False),
        (S.EN_ROUTE, S.CANCELLED_BY_STUDENT, True),
        (S.CLEANING_IN_PROGRESS, S.CANCELLED_BY_STUDENT, False),
        (S.CLEANING_IN_PROGRESS, S.AWAITING_STUDENT_CONFIRMATION, True),
        (S.AWAITING_STUDENT_CONFIRMATION, S.CLOSED_SUCCESSFUL, True),
        (S.DISPUTED, S.CLOSED_SUCCESSFUL, False),
        (S.EN_ROUTE, S.EXPIRED, False),
        (S.CANCELLED_BY_STUDENT, S.SUBMITTED, False),
    ],
)
def test_transition_table(old, new, allowed):
    assert can_transition(old, new) is allowed


def test_transition_changes_state_and_writes_an_event(cleaning_request, resident):
    version = cleaning_request.lock_version
    event = transition(cleaning_request, S.AWAITING_ASSIGNMENT, actor=resident)
    db.session.commit()

    assert cleaning_request.status == S.AWAITING_ASSIGNMENT
    assert cleaning_request.lock_version == version + 1
    assert event.old_state == S.SUBMITTED
    assert event.new_state == S.AWAITING_ASSIGNMENT
    assert event.actor_id == resident.id
    assert cleaning_request.active_student_id == resident.id
    assert cleaning_request.closed_at is None


def test_illegal_transition_is_refused_and_changes_nothing(cleaning_request):
    with pytest.raises(ApiError) as err:
        transition(cleaning_request, S.CLOSED_SUCCESSFUL)
    assert err.value.status == 409
    assert err.value.code == "ILLEGAL_TRANSITION"
    assert cleaning_request.status == S.SUBMITTED
    assert db.session.scalar(db.select(db.func.count(RequestEvent.id))) == 0


def test_terminal_transition_closes_the_request(cleaning_request):
    transition(cleaning_request, S.EXPIRED)
    db.session.commit()
    assert cleaning_request.active_student_id is None
    assert cleaning_request.closed_at is not None


def test_stale_version_is_refused(cleaning_request):
    with pytest.raises(ApiError) as err:
        transition(
            cleaning_request,
            S.AWAITING_ASSIGNMENT,
            expected_version=cleaning_request.lock_version - 1,
        )
    assert err.value.code == "STALE_REQUEST"
    assert cleaning_request.status == S.SUBMITTED


def test_system_events_have_no_actor(cleaning_request):
    event = transition(cleaning_request, S.EXPIRED)
    assert event.actor_id is None


def test_request_events_cannot_be_edited(cleaning_request):
    event = transition(cleaning_request, S.AWAITING_ASSIGNMENT)
    db.session.commit()
    event.event_type = "CHANGED"
    with pytest.raises(RuntimeError):
        db.session.commit()
    db.session.rollback()
