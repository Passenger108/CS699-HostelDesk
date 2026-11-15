from app.cleaning.schemas import iso
from app.hostel_structure.schemas import room_dict
from app.users.models import Role, User
from app.workers.schemas import worker_dict

ROLE_LABELS = {
    Role.STUDENT: "Student",
    Role.WORKER: "Worker",
    Role.SUPERVISOR: "Supervisor",
    Role.SUPER_ADMIN: "Super Admin",
}


def profile_dict(user: User, viewer: User | None = None) -> dict | None:
    viewer = viewer or user
    if user.role == Role.STUDENT and user.student_profile:
        profile = user.student_profile
        data = {"roll_number": profile.roll_number, "room": room_dict(profile.room)}
        if viewer.role == Role.SUPER_ADMIN:
            data["guardian_contact"] = profile.guardian_contact
        return data
    if user.role == Role.WORKER and user.worker_profile:
        return worker_dict(user)
    return None


def account_dict(user: User) -> dict:
    profile = user.student_profile or user.worker_profile
    detail = None
    if user.student_profile:
        detail = f"{profile.roll_number}, room {profile.room.number}"
    elif user.worker_profile:
        detail = " · ".join(filter(None, [profile.employee_id, profile.shift]))
    return {
        **user.to_dict(),
        "role_label": ROLE_LABELS[user.role],
        "detail": detail,
        "created_at": iso(user.created_at),
    }
