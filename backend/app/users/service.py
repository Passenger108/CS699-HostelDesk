from flask import current_app

from app.auth.passwords import hash_password
from app.cleaning.models import AssignmentOffer, OfferStatus
from app.cleaning.service import active_request
from app.common.audit import record_audit
from app.common.errors import fail
from app.credits.service import grant_weekly_credit
from app.extensions import db
from app.hostel_structure.service import find_room
from app.users.models import AccountStatus, Role, StudentProfile, User, WorkerProfile
from app.workers.service import worker_tasks

FIELD_LIMIT = 120
LABELS = {
    "login_id": "Login ID",
    "name": "Name",
    "phone": "Phone",
    "email": "Email",
    "roll_number": "Roll number",
    "room": "Room",
    "guardian_contact": "Guardian contact",
    "employee_id": "Employee ID",
    "shift": "Shift",
}
REQUIRED = {
    Role.STUDENT: ("login_id", "name", "phone", "roll_number", "room"),
    Role.WORKER: ("login_id", "name", "phone", "employee_id"),
    Role.SUPERVISOR: ("login_id", "name"),
    Role.SUPER_ADMIN: ("login_id", "name"),
}


def _fields(data: dict, role: Role) -> dict:
    values = {}
    for key, label in LABELS.items():
        value = data.get(key)
        value = value.strip() if isinstance(value, str) else None
        if value and len(value) > FIELD_LIMIT:
            raise fail("FIELD_TOO_LONG", key, label=label, limit=FIELD_LIMIT)
        if not value and key in REQUIRED[role]:
            raise fail("FIELD_REQUIRED", key, label=label)
        values[key] = value or None
    return values


def _taken(model, column, value) -> bool:
    return db.session.scalar(db.select(model).filter(column == value)) is not None


def list_users(role: str | None = None) -> list[User]:
    query = db.select(User).order_by(User.role, User.name)
    if role:
        try:
            query = query.filter_by(role=Role(role))
        except ValueError:
            raise fail("BAD_ROLE", "role") from None
    return list(db.session.scalars(query))


def create_user(admin: User, data: dict) -> User:
    try:
        role = Role(data.get("role"))
    except ValueError:
        raise fail("BAD_ROLE", "role") from None
    values = _fields(data, role)
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    length = current_app.config["PASSWORD_MIN_LENGTH"]
    if len(password) < length:
        raise fail("SHORT_PASSWORD", "password", length=length)
    if _taken(User, User.login_id, values["login_id"]):
        raise fail("LOGIN_TAKEN", "login_id", login_id=values["login_id"])

    user = User(
        role=role,
        login_id=values["login_id"],
        name=values["name"],
        phone=values["phone"],
        email=values["email"],
        password_hash=hash_password(password),
    )
    if role == Role.STUDENT:
        room = find_room(values["room"].upper())
        if room is None:
            raise fail("ROOM_NOT_FOUND", "room", room=values["room"])
        if _taken(StudentProfile, StudentProfile.roll_number, values["roll_number"]):
            raise fail("ROLL_TAKEN", "roll_number", value=values["roll_number"])
        user.student_profile = StudentProfile(
            roll_number=values["roll_number"],
            room=room,
            guardian_contact=values["guardian_contact"],
        )
    if role == Role.WORKER:
        if _taken(WorkerProfile, WorkerProfile.employee_id, values["employee_id"]):
            raise fail("EMPLOYEE_TAKEN", "employee_id", value=values["employee_id"])
        user.worker_profile = WorkerProfile(
            employee_id=values["employee_id"], shift=values["shift"]
        )
    db.session.add(user)
    db.session.flush()
    if role == Role.STUDENT:
        grant_weekly_credit(user)
    record_audit(
        "USER_CREATED",
        "user",
        user.id,
        actor=admin,
        after={"login_id": user.login_id, "role": role.value},
    )
    db.session.commit()
    return user


def has_active_work(user: User) -> bool:
    if user.role == Role.STUDENT:
        return active_request(user) is not None
    if user.role == Role.WORKER:
        pending = db.select(AssignmentOffer).filter_by(
            worker_id=user.id, status=OfferStatus.PENDING
        )
        return bool(worker_tasks(user.id)) or db.session.scalar(pending) is not None
    return False


def set_status(admin: User, user_id: int, status) -> User:
    user = db.session.get(User, user_id)
    if user is None:
        raise fail("USER_NOT_FOUND")
    if status not in (AccountStatus.ACTIVE.value, AccountStatus.DISABLED.value):
        raise fail("BAD_STATUS", "account_status")
    if user.id == admin.id:
        raise fail("OWN_ACCOUNT")
    new = AccountStatus(status)
    if new == AccountStatus.DISABLED and has_active_work(user):
        raise fail("HAS_ACTIVE_WORK")
    if user.account_status == new:
        return user
    before = user.account_status.value
    user.account_status = new
    user.failed_login_count = 0
    user.first_failed_login_at = user.locked_until = None
    user.token_version += 1
    record_audit(
        "USER_ENABLED" if new == AccountStatus.ACTIVE else "USER_DISABLED",
        "user",
        user.id,
        actor=admin,
        before={"account_status": before},
        after={"account_status": new.value},
    )
    db.session.commit()
    return user
