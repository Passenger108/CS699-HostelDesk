import click
from flask import Flask

from app.auth.passwords import hash_password
from app.extensions import db
from app.hostel_structure.service import HOSTEL_4, find_room, seed_hostel_4
from app.users.models import Role, StudentProfile, User, WorkerProfile

DEMO_PASSWORD = "hosteldesk-demo-2026"
DEMO_USERS = [
    ("demo.student", Role.STUDENT, "Demo Student (fictional)"),
    ("demo.worker", Role.WORKER, "Demo Worker (fictional)"),
    ("demo.supervisor", Role.SUPERVISOR, "Demo Supervisor (fictional)"),
    ("demo.admin", Role.SUPER_ADMIN, "Demo Super Admin (fictional)"),
    ("demo.student2", Role.STUDENT, "Aarav Demo (fictional)"),
    ("demo.student3", Role.STUDENT, "Diya Demo (fictional)"),
    ("demo.student4", Role.STUDENT, "Kabir Demo (fictional)"),
    ("demo.student5", Role.STUDENT, "Meera Demo (fictional)"),
    ("demo.student6", Role.STUDENT, "Rohan Demo (fictional)"),
    ("demo.worker2", Role.WORKER, "Sunil Demo (fictional)"),
    ("demo.worker3", Role.WORKER, "Lata Demo (fictional)"),
]
DEMO_STUDENTS = {
    "demo.student": ("DEMO24B001", "A105"),
    "demo.student2": ("DEMO24B002", "B203"),
    "demo.student3": ("DEMO24B003", "C307"),
    "demo.student4": ("DEMO24B004", "D412"),
    "demo.student5": ("DEMO24B005", "E509"),
    "demo.student6": ("DEMO24B006", "F614"),
}
DEMO_WORKERS = {
    "demo.worker": ("DEMO-W01", "Morning"),
    "demo.worker2": ("DEMO-W02", "Morning"),
    "demo.worker3": ("DEMO-W03", "Evening"),
}


def _seed_profile(user: User) -> bool:
    if user.login_id in DEMO_STUDENTS and user.student_profile is None:
        roll_number, room_number = DEMO_STUDENTS[user.login_id]
        user.student_profile = StudentProfile(
            roll_number=roll_number,
            room=find_room(room_number),
            guardian_contact="Demo Guardian (fictional), +91 90000 00000",
        )
        return True
    if user.login_id in DEMO_WORKERS and user.worker_profile is None:
        employee_id, shift = DEMO_WORKERS[user.login_id]
        user.worker_profile = WorkerProfile(employee_id=employee_id, shift=shift)
        return True
    return False


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-demo")
    def seed_demo():
        _, created = seed_hostel_4()
        click.echo(f"{'created ' if created else 'exists  '} {HOSTEL_4['name']} structure")

        for login_id, role, name in DEMO_USERS:
            user = db.session.scalar(db.select(User).filter_by(login_id=login_id))
            if user:
                status = "profile " if _seed_profile(user) else "exists  "
                click.echo(f"{status} {login_id}")
                continue
            user = User(
                login_id=login_id,
                role=role,
                name=name,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.session.add(user)
            _seed_profile(user)
            click.echo(f"created  {login_id}")
        db.session.commit()
        click.echo(f"Demo password for all accounts: {DEMO_PASSWORD}")
