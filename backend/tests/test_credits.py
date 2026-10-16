from datetime import datetime, timedelta

import pytest

from app.common.errors import ApiError
from app.common.settings import set_setting
from app.common.time import HOSTEL_TZ
from app.credits.models import CreditEntry, CreditEntryType, CreditType
from app.credits.service import (
    balance,
    consume_credit,
    grant_goodwill,
    grant_weekly_credit,
    grant_weekly_credits,
    history,
    release_credit,
    reserve_credit,
)
from app.extensions import db
from app.users.models import AccountStatus, Role

MONDAY = datetime(2026, 10, 19, 9, 0, tzinfo=HOSTEL_TZ)


def week(n):
    return MONDAY + timedelta(weeks=n)


@pytest.fixture
def student(make_user):
    return make_user(login_id="stu", role=Role.STUDENT)


@pytest.fixture
def supervisor(make_user):
    return make_user(login_id="sup", role=Role.SUPERVISOR)


def test_one_credit_per_week(student):
    assert grant_weekly_credit(student, MONDAY) == "granted"
    assert balance(student.id, MONDAY)["available"] == 1


def test_running_twice_in_the_same_week_grants_once(student):
    grant_weekly_credit(student, MONDAY)
    assert grant_weekly_credit(student, MONDAY + timedelta(days=3)) == "already"
    assert balance(student.id, MONDAY)["available"] == 1


def test_week_starts_monday_midnight_india_time(student):
    sunday_night = datetime(2026, 10, 25, 23, 59, tzinfo=HOSTEL_TZ)
    monday_morning = datetime(2026, 10, 26, 0, 0, tzinfo=HOSTEL_TZ)
    assert grant_weekly_credit(student, sunday_night) == "granted"
    assert grant_weekly_credit(student, monday_morning) == "granted"


def test_unused_credits_carry_forward_up_to_cap(student):
    results = [grant_weekly_credit(student, week(n)) for n in range(5)]
    assert results == ["granted", "granted", "granted", "capped", "capped"]
    assert balance(student.id, week(4))["available"] == 3


def test_capped_week_is_not_granted_later_that_week(student):
    for n in range(3):
        grant_weekly_credit(student, week(n))
    assert grant_weekly_credit(student, week(3)) == "capped"
    reserve_credit(student, request_id=1, now=week(3))
    assert grant_weekly_credit(student, week(3) + timedelta(days=1)) == "already"


def test_reserved_credits_count_towards_cap(student):
    for n in range(3):
        grant_weekly_credit(student, week(n))
    reserve_credit(student, request_id=1, now=week(2))
    assert grant_weekly_credit(student, week(3)) == "capped"
    release_credit(student, request_id=1, reason="Cancelled")
    assert balance(student.id, week(3))["available"] == 3


def test_cap_follows_setting(student, supervisor):
    set_setting("credit_cap", 1, supervisor, "Short term")
    assert grant_weekly_credit(student, week(0)) == "granted"
    assert grant_weekly_credit(student, week(1)) == "capped"


def test_weekly_grant_skips_inactive_students_and_staff(make_user, student):
    make_user(login_id="gone", role=Role.STUDENT, account_status=AccountStatus.DISABLED)
    make_user(login_id="wrk", role=Role.WORKER)
    assert grant_weekly_credits(MONDAY) == {"granted": 1, "capped": 0, "already": 0}


def test_reserve_then_consume(student):
    grant_weekly_credit(student, MONDAY)
    assert reserve_credit(student, request_id=7, now=MONDAY) == CreditType.STANDARD
    after_reserve = balance(student.id, MONDAY)
    assert (after_reserve["available"], after_reserve["reserved"]) == (0, 1)
    consume_credit(student, request_id=7, reason="Cleaning confirmed")
    after_consume = balance(student.id, MONDAY)
    assert (after_consume["available"], after_consume["reserved"]) == (0, 0)
    assert after_consume["consumed"] == 1


def test_release_returns_the_credit(student):
    grant_weekly_credit(student, MONDAY)
    reserve_credit(student, request_id=7, now=MONDAY)
    release_credit(student, request_id=7, reason="Cancelled by student")
    current = balance(student.id, MONDAY)
    assert (current["available"], current["reserved"], current["consumed"]) == (1, 0, 0)


def test_reserve_without_credit_is_refused(student):
    with pytest.raises(ApiError) as err:
        reserve_credit(student, request_id=1, now=MONDAY)
    assert err.value.code == "NO_CREDIT"


def test_same_request_cannot_reserve_twice(student):
    grant_weekly_credit(student, week(0))
    grant_weekly_credit(student, week(1))
    reserve_credit(student, request_id=1, now=week(1))
    with pytest.raises(ApiError) as err:
        reserve_credit(student, request_id=1, now=week(1))
    assert err.value.code == "ALREADY_RESERVED"


def test_release_or_consume_needs_a_reservation(student):
    grant_weekly_credit(student, MONDAY)
    reserve_credit(student, request_id=1, now=MONDAY)
    consume_credit(student, request_id=1, reason="Done")
    for action in (release_credit, consume_credit):
        with pytest.raises(ApiError) as err:
            action(student, request_id=1, reason="Again")
        assert err.value.code == "NO_RESERVATION"


def test_goodwill_ignores_cap_and_is_used_first(student, supervisor):
    for n in range(3):
        grant_weekly_credit(student, week(n))
    grant_goodwill(student, supervisor, "Valid complaint", now=week(2))
    current = balance(student.id, week(2))
    assert (current["available"], current["goodwill_available"]) == (4, 1)
    assert reserve_credit(student, request_id=1, now=week(2)) == CreditType.GOODWILL
    assert balance(student.id, week(2))["standard_available"] == 3


def test_goodwill_expires_next_monday(student, supervisor):
    wednesday = MONDAY + timedelta(days=2)
    grant_goodwill(student, supervisor, "Valid complaint", now=wednesday)
    assert balance(student.id, wednesday)["goodwill_available"] == 1
    next_monday = MONDAY + timedelta(weeks=1, hours=-9)
    assert balance(student.id, next_monday)["goodwill_available"] == 0

    grant_weekly_credit(student, next_monday)
    expired = db.session.scalars(
        db.select(CreditEntry).filter_by(entry_type=CreditEntryType.EXPIRE)
    ).all()
    assert len(expired) == 1


def test_goodwill_requires_reason_and_student(student, supervisor):
    with pytest.raises(ApiError):
        grant_goodwill(student, supervisor, "  ", now=MONDAY)
    with pytest.raises(ApiError):
        grant_goodwill(supervisor, supervisor, "Reason", now=MONDAY)


def test_ledger_rows_cannot_be_edited(student):
    grant_weekly_credit(student, MONDAY)
    entry = db.session.scalar(db.select(CreditEntry))
    entry.quantity = 5
    with pytest.raises(RuntimeError):
        db.session.flush()
    db.session.rollback()


def test_history_is_newest_first(student):
    grant_weekly_credit(student, MONDAY)
    reserve_credit(student, request_id=3, now=MONDAY)
    types = [row["entry_type"] for row in history(student.id)]
    assert types == ["RESERVE", "WEEKLY_GRANT"]
