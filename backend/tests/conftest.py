import pytest

from app import create_app
from app.auth.passwords import hash_password
from app.extensions import db as _db
from app.hostel_structure.service import seed_hostel
from app.users.models import Role, User

PASSWORD = "correct-horse-battery"


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    def _make(login_id="student1", role=Role.STUDENT, **kwargs):
        user = User(
            login_id=login_id,
            role=role,
            name=kwargs.pop("name", "Test User"),
            password_hash=hash_password(kwargs.pop("password", PASSWORD)),
            **kwargs,
        )
        _db.session.add(user)
        _db.session.commit()
        return user

    return _make


@pytest.fixture
def login(client):
    def _login(login_id="student1", password=PASSWORD):
        return client.post("/api/v1/auth/login", json={"login_id": login_id, "password": password})

    return _login


@pytest.fixture
def hostel(app):
    hostel, _ = seed_hostel(
        code="H4",
        name="Hostel 4",
        floors=2,
        wings="AB",
        rooms_per_wing=3,
        facilities=["Reception desk"],
    )
    _db.session.commit()
    return hostel


@pytest.fixture
def auth_get(client, login):
    def _get(url, login_id="student1"):
        token = login(login_id).get_json()["access_token"]
        return client.get(url, headers={"Authorization": f"Bearer {token}"})

    return _get
