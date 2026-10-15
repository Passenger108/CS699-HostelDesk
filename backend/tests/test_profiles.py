from app.extensions import db
from app.hostel_structure.models import Location, LocationKind
from app.hostel_structure.service import find_room
from app.users.models import Role, StudentProfile, WorkerProfile
from app.users.service import profile_dict


def make_student(make_user, login_id="student1"):
    user = make_user(login_id=login_id, role=Role.STUDENT)
    user.student_profile = StudentProfile(
        roll_number="24B0001", room=find_room("B203"), guardian_contact="Parent, 9000000000"
    )
    db.session.commit()
    return user


def test_me_includes_student_room(make_user, auth_get, hostel):
    make_student(make_user)
    body = auth_get("/api/v1/me").get_json()
    assert body["profile"]["roll_number"] == "24B0001"
    assert body["profile"]["room"] == {
        "id": body["profile"]["room"]["id"],
        "number": "B203",
        "floor": 2,
        "floor_label": "Floor 2",
        "wing": "B",
    }


def test_student_does_not_see_guardian_contact(make_user, auth_get, hostel):
    make_student(make_user)
    assert "guardian_contact" not in auth_get("/api/v1/me").get_json()["profile"]


def test_super_admin_sees_guardian_contact(make_user, hostel):
    student = make_student(make_user)
    admin = make_user(login_id="admin", role=Role.SUPER_ADMIN)
    assert profile_dict(student, viewer=admin)["guardian_contact"] == "Parent, 9000000000"


def test_me_includes_worker_profile(make_user, auth_get, hostel):
    worker = make_user(login_id="worker1", role=Role.WORKER)
    location = db.session.scalar(db.select(Location).filter_by(kind=LocationKind.FLOOR_WING))
    worker.worker_profile = WorkerProfile(
        employee_id="W-01", shift="Morning", last_location=location
    )
    db.session.commit()

    profile = auth_get("/api/v1/me", login_id="worker1").get_json()["profile"]
    assert profile["employee_id"] == "W-01"
    assert profile["availability"] == "AVAILABLE"
    assert profile["last_location"]["label"] == "Floor 1, Wing A"


def test_supervisor_has_no_profile(make_user, auth_get):
    make_user(login_id="sup", role=Role.SUPERVISOR)
    assert auth_get("/api/v1/me", login_id="sup").get_json()["profile"] is None
