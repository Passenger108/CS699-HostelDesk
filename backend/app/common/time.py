from datetime import date, datetime, time, timedelta, timezone

from app.common.models import as_utc

HOSTEL_TZ = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


def hostel_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(HOSTEL_TZ)


def clock(value: datetime) -> str:
    local = hostel_now(as_utc(value))
    return f"{local.hour % 12 or 12}:{local:%M} {'am' if local.hour < 12 else 'pm'}"


def week_start(now: datetime | None = None) -> date:
    local = hostel_now(now)
    return local.date() - timedelta(days=local.weekday())


def week_start_at(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=HOSTEL_TZ).astimezone(timezone.utc)


def next_week_start_at(now: datetime | None = None) -> datetime:
    return week_start_at(week_start(now) + timedelta(days=7))
