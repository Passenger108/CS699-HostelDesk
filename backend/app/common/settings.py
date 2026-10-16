from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.audit import record_audit
from app.common.errors import ApiError
from app.common.models import IdMixin, TimestampMixin
from app.extensions import db

DEFAULT_SETTINGS: dict[str, Any] = {
    "credit_cap": 3,
    "reschedule_hours": 24,
}


class Setting(IdMixin, TimestampMixin, db.Model):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("key", "version"),)

    key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)


def _latest(key: str) -> Setting | None:
    return db.session.scalar(
        db.select(Setting).filter_by(key=key).order_by(Setting.version.desc()).limit(1)
    )


def get_setting(key: str) -> Any:
    if key not in DEFAULT_SETTINGS:
        raise KeyError(key)
    latest = _latest(key)
    return latest.value if latest else DEFAULT_SETTINGS[key]


def set_setting(key: str, value: Any, actor, reason: str) -> Setting:
    if key not in DEFAULT_SETTINGS:
        raise ApiError(400, "UNKNOWN_SETTING", f"There is no setting called {key}.")
    if not reason or not reason.strip():
        raise ApiError(400, "REASON_REQUIRED", "A reason is required to change a setting.")
    latest = _latest(key)
    old_value = latest.value if latest else DEFAULT_SETTINGS[key]
    setting = Setting(
        key=key,
        version=(latest.version + 1) if latest else 1,
        value=value,
        changed_by_id=actor.id if actor is not None else None,
        reason=reason.strip(),
    )
    db.session.add(setting)
    record_audit(
        "SETTING_CHANGED",
        "setting",
        key,
        actor=actor,
        before={"value": old_value},
        after={"value": value, "version": setting.version},
        reason=reason.strip(),
    )
    return setting
