import click
from flask import Flask

from app.auth.passwords import hash_password
from app.extensions import db
from app.users.models import Role, User

DEMO_PASSWORD = "hosteldesk-demo-2026"
DEMO_USERS = [
    ("demo.student", Role.STUDENT, "Demo Student (fictional)"),
    ("demo.worker", Role.WORKER, "Demo Worker (fictional)"),
    ("demo.supervisor", Role.SUPERVISOR, "Demo Supervisor (fictional)"),
    ("demo.admin", Role.SUPER_ADMIN, "Demo Super Admin (fictional)"),
]


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-demo")
    def seed_demo():
        for login_id, role, name in DEMO_USERS:
            if db.session.scalar(db.select(User).filter_by(login_id=login_id)):
                click.echo(f"exists   {login_id}")
                continue
            db.session.add(
                User(
                    login_id=login_id,
                    role=role,
                    name=name,
                    password_hash=hash_password(DEMO_PASSWORD),
                )
            )
            click.echo(f"created  {login_id}")
        db.session.commit()
        click.echo(f"Demo password for all accounts: {DEMO_PASSWORD}")
