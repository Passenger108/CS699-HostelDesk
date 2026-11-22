from datetime import datetime, time
from io import BytesIO

import click
from flask import Flask
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.auth.passwords import hash_password
from app.cleaning.arrival import answer_door, arrive, set_off, start_cleaning
from app.cleaning.completion import CHECKLIST, add_proof, complete, confirm, dispute
from app.cleaning.models import CleaningRequest, Feedback, RequestStatus, TaskMessage
from app.cleaning.service import (
    accept_offer,
    active_request,
    approve_request,
    offer_request,
    submit_request,
)
from app.cleaning.timers import run_due
from app.common.errors import ApiError
from app.common.time import HOSTEL_TZ, hostel_now
from app.credits.service import grant_weekly_credits
from app.extensions import db
from app.hostel_structure.service import HOSTEL_4, find_location, find_room, seed_hostel_4
from app.users.models import Role, StudentProfile, User, WorkerProfile
from app.workers.service import update_location

TIMER_LABELS = {
    "offers_timed_out": "Offers timed out",
    "arrivals_closed": "Door waits closed",
    "delays_escalated": "Delays sent to the supervisor",
    "windows_missed": "Time windows missed",
    "requests_expired": "Requests expired",
    "confirmations_closed": "Cleanings closed without an answer",
    "locations_reminded": "Location reminders sent",
}
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
    ("demo.student7", Role.STUDENT, "Isha Demo (fictional)"),
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
    "demo.student7": ("DEMO24B007", "G708"),
}
DEMO_WORKERS = {
    "demo.worker": ("DEMO-W01", "Morning"),
    "demo.worker2": ("DEMO-W02", "Morning"),
    "demo.worker3": ("DEMO-W03", "Evening"),
}
DEMO_REQUESTS = [
    ("demo.student3", "ANY_TIME_TODAY", "NORMAL", None, False),
    ("demo.student4", "AVAILABLE_NOW", "URGENT", "Water leaked under the bed", False),
    ("demo.student5", "ANY_TIME_TODAY", "NORMAL", None, True),
    ("demo.student6", "AVAILABLE_NOW", "NORMAL", None, False),
]
DEMO_LOCATIONS = {"demo.worker": (5, "E"), "demo.worker2": (4, "D")}


def _demo_phone(login_id: str) -> str:
    position = [entry[0] for entry in DEMO_USERS].index(login_id) + 1
    return f"+91 90000 {position:05d}"


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


def _user(login_id: str) -> User | None:
    return db.session.scalar(db.select(User).filter_by(login_id=login_id))


def _demo_photo() -> FileStorage:
    out = BytesIO()
    Image.new("RGB", (800, 600), (214, 228, 240)).save(out, "PNG")
    out.seek(0)
    return FileStorage(out, filename="demo-room.png", content_type="image/png")


def _seed_cleaned(supervisor: User, login_id: str, note: str, chat: list[tuple[str, str]]):
    student, worker = _user(login_id), _user("demo.worker3")
    if active_request(student):
        return None
    request, _ = submit_request(student, "AVAILABLE_NOW", note=note)
    approve_request(request, supervisor)
    offer_request(request, supervisor, worker.id, request.lock_version)
    accept_offer(request.offers[-1], worker, 5)
    for sender, body in chat:
        db.session.add(TaskMessage(request=request, sender=_user(sender), body=body))
    set_off(request, worker)
    arrive(request, worker)
    answer_door(request, student, "COME_IN")
    start_cleaning(request, worker)
    add_proof(request, worker, _demo_photo())
    return complete(request, worker, dict.fromkeys(CHECKLIST, True))


def _rate(request: CleaningRequest) -> str:
    confirm(request, request.student)
    db.session.add(Feedback(request=request, worker_id=request.assigned_worker_id, rating=4))
    db.session.commit()
    return "rated   "


def _dispute(request: CleaningRequest) -> str:
    dispute(request, request.student, "The balcony was not cleaned.")
    return "disputed"


DEMO_HISTORY = [
    (
        "demo.student7",
        "The fan is very dusty",
        [
            ("demo.worker3", "I will reach in 5 minutes."),
            ("demo.student7", "Okay, I am in my room."),
        ],
        _rate,
    ),
    (
        "demo.student2",
        "Please do the balcony too",
        [("demo.student2", "Please clean the balcony as well.")],
        _dispute,
    ),
]


def _seed_history(supervisor: User) -> None:
    for login_id, note, chat, finish in DEMO_HISTORY:
        try:
            request = _seed_cleaned(supervisor, login_id, note, chat)
        except ApiError as err:
            click.echo(f"skipped  {login_id}: {err.message}")
            continue
        if request:
            click.echo(f"{finish(request)} request {request.id} by {login_id} after demo.worker3")


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-demo")
    def seed_demo():
        _, created = seed_hostel_4()
        click.echo(f"{'created ' if created else 'exists  '} {HOSTEL_4['name']} structure")

        for login_id, role, name in DEMO_USERS:
            user = db.session.scalar(db.select(User).filter_by(login_id=login_id))
            if user:
                added_phone = user.phone is None
                if added_phone:
                    user.phone = _demo_phone(login_id)
                status = "updated " if _seed_profile(user) or added_phone else "exists  "
                click.echo(f"{status} {login_id}")
                continue
            user = User(
                login_id=login_id,
                role=role,
                name=name,
                phone=_demo_phone(login_id),
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.session.add(user)
            _seed_profile(user)
            click.echo(f"created  {login_id}")
        db.session.flush()
        summary = grant_weekly_credits()
        db.session.commit()
        click.echo(f"Weekly credits: {_summary_text(summary)}")
        click.echo(f"Demo password for all accounts: {DEMO_PASSWORD}")

    @app.cli.command("seed-demo-requests")
    def seed_demo_requests():
        supervisor = db.session.scalar(db.select(User).filter_by(login_id="demo.supervisor"))
        if supervisor is None:
            raise click.ClickException("Run flask seed-demo first.")
        for login_id, mode, priority, reason, approve in DEMO_REQUESTS:
            student = db.session.scalar(db.select(User).filter_by(login_id=login_id))
            try:
                request, created = submit_request(
                    student,
                    mode,
                    priority=priority,
                    urgent_reason=reason,
                    client_key=f"demo-{login_id}-{hostel_now().date()}",
                )
                if approve:
                    approve_request(request, supervisor)
            except ApiError as err:
                click.echo(f"skipped  {login_id}: {err.message}")
                continue
            status = "created " if created else "exists  "
            click.echo(f"{status} request {request.id} for {login_id}: {request.status.value}")
        for login_id, (floor, wing) in DEMO_LOCATIONS.items():
            worker = db.session.scalar(db.select(User).filter_by(login_id=login_id))
            location = find_location(floor, wing)
            update_location(worker, location.id)
            click.echo(f"placed   {login_id} at {location.label}")
        waiting = db.session.scalar(
            db.select(CleaningRequest).filter_by(status=RequestStatus.AWAITING_ASSIGNMENT)
        )
        if waiting:
            worker = db.session.scalar(db.select(User).filter_by(login_id="demo.worker"))
            offer_request(waiting, supervisor, worker.id, waiting.lock_version)
            click.echo(f"offered  request {waiting.id} to demo.worker")
        worker = db.session.scalar(db.select(User).filter_by(login_id="demo.worker2"))
        for login_id, eta in (("demo.student6", 15), ("demo.student4", 10)):
            request = db.session.scalar(
                db.select(CleaningRequest)
                .join(User, CleaningRequest.student_id == User.id)
                .filter(
                    User.login_id == login_id, CleaningRequest.status == RequestStatus.SUBMITTED
                )
            )
            if request:
                approve_request(request, supervisor)
                offer_request(request, supervisor, worker.id, request.lock_version)
                accept_offer(request.offers[-1], worker, eta)
                click.echo(f"accepted request {request.id} by demo.worker2, ETA {eta} min")
        _seed_history(supervisor)

    @app.cli.command("grant-weekly-credits")
    @click.option(
        "--date",
        "on_date",
        type=click.DateTime(formats=["%Y-%m-%d"]),
        help="Run as if it were this date (YYYY-MM-DD), for demos and testing.",
    )
    def grant_weekly_credits_command(on_date):
        now = datetime.combine(on_date.date(), time(12), tzinfo=HOSTEL_TZ) if on_date else None
        summary = grant_weekly_credits(now)
        db.session.commit()
        click.echo(f"Weekly credits: {_summary_text(summary)}")

    @app.cli.command("run-timers")
    def run_timers_command():
        result = run_due()
        for key, label in TIMER_LABELS.items():
            click.echo(f"{label}: {result[key]}")
        click.echo(f"Weekly credits: {_summary_text(result['weekly_credits'])}")


def _summary_text(summary: dict) -> str:
    return (
        f"{summary['granted']} granted, {summary['capped']} at the limit, "
        f"{summary['already']} already had this week's credit"
    )
