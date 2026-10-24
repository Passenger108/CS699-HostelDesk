from app.common.models import utcnow
from app.hostel_structure.service import room_dict
from app.users.models import Role, User
from app.workers.service import worker_fields


def profile_dict(user: User, viewer: User | None = None) -> dict | None:
    viewer = viewer or user
    if user.role == Role.STUDENT and user.student_profile:
        profile = user.student_profile
        data = {"roll_number": profile.roll_number, "room": room_dict(profile.room)}
        if viewer.role == Role.SUPER_ADMIN:
            data["guardian_contact"] = profile.guardian_contact
        return data
    if user.role == Role.WORKER and user.worker_profile:
        return worker_fields(user.worker_profile, utcnow())
    return None
