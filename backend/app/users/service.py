from app.common.models import as_utc
from app.hostel_structure.service import location_dict, room_dict
from app.users.models import Role, User


def profile_dict(user: User, viewer: User | None = None) -> dict | None:
    viewer = viewer or user
    if user.role == Role.STUDENT and user.student_profile:
        profile = user.student_profile
        data = {"roll_number": profile.roll_number, "room": room_dict(profile.room)}
        if viewer.role == Role.SUPER_ADMIN:
            data["guardian_contact"] = profile.guardian_contact
        return data
    if user.role == Role.WORKER and user.worker_profile:
        profile = user.worker_profile
        updated_at = as_utc(profile.location_updated_at)
        return {
            "employee_id": profile.employee_id,
            "shift": profile.shift,
            "availability": profile.availability.value,
            "last_location": location_dict(profile.last_location),
            "location_updated_at": updated_at.isoformat() if updated_at else None,
        }
    return None
