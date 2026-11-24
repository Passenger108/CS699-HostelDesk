import re

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

ROOM_LIMIT = 2
ID_LIMIT = 32
SHIFTS = ("Morning", "Evening", "Night")
LABELS = {
    "login_id": "Login ID",
    "name": "Name",
    "phone": "Phone",
    "email": "Email",
    "roll_number": "Roll number",
    "room": "Room",
    "employee_id": "Employee ID",
    "shift": "Shift",
}
RULES = {
    "login_id": (
        r"[a-z][a-z0-9._-]{2,29}",
        "must be 3 to 30 characters: small letters, digits, dot, dash or underscore, "
        "starting with a letter (for example demo.student8).",
    ),
    "name": (
        r"[A-Za-z][A-Za-z .'-]{0,58}[A-Za-z.]",
        "must be 2 to 60 letters, with spaces, dots, dashes or apostrophes only.",
    ),
    "phone": (
        r"(?:\+?91|0)?([6-9]\d{9})",
        "must be a 10-digit Indian mobile number starting with 6, 7, 8 or 9 "
        "(for example +91 98765 43210).",
    ),
    "email": (
        r"[^@\s]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
        "must look like name@example.com.",
    ),
    "shift": ("|".join(SHIFTS), f"must be one of {', '.join(SHIFTS)}."),
}
CLEAN = {
    "login_id": str.lower,
    "phone": lambda v: re.sub(r"[\s-]", "", v),
    "email": str.lower,
    "roll_number": str.upper,
    "room": str.upper,
    "employee_id": str.upper,
    "shift": str.capitalize,
}
REQUIRED = {
    Role.STUDENT: ("login_id", "name", "phone", "roll_number", "room"),
    Role.WORKER: ("login_id", "name", "phone", "employee_id", "shift"),
    Role.SUPERVISOR: ("login_id", "name"),
    Role.SUPER_ADMIN: ("login_id", "name"),
}
UNIQUE = {"phone": User.phone, "email": User.email}
ROLE_FIELDS = {Role.STUDENT: ("roll_number", "room"), Role.WORKER: ("employee_id", "shift")}


def _field(data: dict, key: str, role: Role) -> str | None:
    value = data.get(key)
    value = " ".join(value.split()) if isinstance(value, str) else ""
    if not value:
        if key in REQUIRED[role]:
            raise fail("FIELD_REQUIRED", key, label=LABELS[key])
        return None
    value = CLEAN.get(key, str)(value)
    if key not in RULES:
        if len(value) > ID_LIMIT:
            raise fail("FIELD_TOO_LONG", key, label=LABELS[key], limit=ID_LIMIT)
        return value
    pattern, rule = RULES[key]
    match = re.fullmatch(pattern, value)
    if not match:
        raise fail("BAD_FORMAT", key, label=LABELS[key], rule=rule)
    if key == "phone":
        value = f"+91 {match[1][:5]} {match[1][5:]}"
    return value


def _fields(data: dict, role: Role) -> dict:
    keys = ("login_id", "name", "phone", "email", *ROLE_FIELDS.get(role, ()))
    values = {key: _field(data, key, role) for key in keys}
    for key, column in UNIQUE.items():
        if values[key] and _taken(User, column, values[key]):
            raise fail("VALUE_TAKEN", key, label=LABELS[key].lower(), value=values[key])
    return values


def room_is_full(room, leaving: User | None = None) -> bool:
    query = (
        db.select(db.func.count())
        .select_from(StudentProfile)
        .join(User)
        .filter(
            StudentProfile.room_id == room.id,
            User.account_status == AccountStatus.ACTIVE,
            User.id != (leaving.id if leaving else None),
        )
    )
    return db.session.scalar(query) >= ROOM_LIMIT


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
        room = find_room(values["room"])
        if room is None:
            raise fail("ROOM_NOT_FOUND", "room", room=values["room"])
        if room_is_full(room):
            raise fail("ROOM_FULL", "room", room=room.number, limit=ROOM_LIMIT)
        if _taken(StudentProfile, StudentProfile.roll_number, values["roll_number"]):
            raise fail("ROLL_TAKEN", "roll_number", value=values["roll_number"])
        user.student_profile = StudentProfile(roll_number=values["roll_number"], room=room)
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
    profile = user.student_profile
    if new == AccountStatus.ACTIVE and profile and room_is_full(profile.room, user):
        raise fail("ROOM_FULL", room=profile.room.number, limit=ROOM_LIMIT)
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
