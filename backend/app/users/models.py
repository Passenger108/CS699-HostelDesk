import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import IdMixin, TimestampMixin
from app.extensions import db
from app.hostel_structure.models import Location, Room


class Role(str, enum.Enum):
    STUDENT = "STUDENT"
    WORKER = "WORKER"
    SUPERVISOR = "SUPERVISOR"
    SUPER_ADMIN = "SUPER_ADMIN"


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    LOCKED = "LOCKED"


class Locale(str, enum.Enum):
    EN = "en"
    HI = "hi"
    MR = "mr"


class WorkerAvailability(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFF_DUTY = "OFF_DUTY"


class User(IdMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    login_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[Locale] = mapped_column(
        Enum(Locale, name="user_locale", values_callable=lambda e: [m.value for m in e]),
        default=Locale.EN,
        nullable=False,
    )
    avatar_key: Mapped[str | None] = mapped_column(String(255))
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"), default=AccountStatus.ACTIVE, nullable=False
    )

    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    first_failed_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(default=0, nullable=False)

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    worker_profile: Mapped["WorkerProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role.value,
            "login_id": self.login_id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "locale": self.locale.value,
            "account_status": self.account_status.value,
        }


class StudentProfile(TimestampMixin, db.Model):
    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    roll_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    guardian_contact: Mapped[str | None] = mapped_column(String(120))

    user: Mapped[User] = relationship(back_populates="student_profile")
    room: Mapped["Room"] = relationship()


class WorkerProfile(TimestampMixin, db.Model):
    __tablename__ = "worker_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    shift: Mapped[str | None] = mapped_column(String(40))
    availability: Mapped[WorkerAvailability] = mapped_column(
        Enum(WorkerAvailability, name="worker_availability"),
        default=WorkerAvailability.AVAILABLE,
        nullable=False,
    )
    last_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    off_duty_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="worker_profile")
    last_location: Mapped["Location | None"] = relationship()
