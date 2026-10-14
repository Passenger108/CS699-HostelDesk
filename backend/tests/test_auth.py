from datetime import timedelta

from app.common.models import utcnow
from app.extensions import db
from app.users.models import AccountStatus, Role, User
from tests.conftest import PASSWORD


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/api/v1/health").get_json() == {"status": "ok"}


def test_login_success_returns_tokens_and_user(make_user, login):
    make_user(role=Role.SUPERVISOR)
    res = login()
    assert res.status_code == 200
    body = res.get_json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["role"] == "SUPERVISOR"
    assert "password_hash" not in body["user"]


def test_wrong_password_and_unknown_id_look_identical(make_user, login):
    make_user()
    wrong = login(password="not-the-password")
    unknown = login(login_id="nobody")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json()


def test_missing_fields_rejected(client):
    res = client.post("/api/v1/auth/login", json={"login_id": "x"})
    assert res.status_code == 400


def test_five_failures_lock_account(app, make_user, login):
    user = make_user()
    for _ in range(5):
        assert login(password="wrong").status_code == 401
    db.session.refresh(user)
    assert user.account_status == AccountStatus.LOCKED
    assert login().status_code == 401


def test_success_resets_failure_counter(make_user, login):
    user = make_user()
    for _ in range(4):
        login(password="wrong")
    assert login().status_code == 200
    db.session.refresh(user)
    assert user.failed_login_count == 0
    for _ in range(4):
        login(password="wrong")
    db.session.refresh(user)
    assert user.account_status == AccountStatus.ACTIVE


def test_lock_expires_automatically(make_user, login):
    user = make_user()
    user.account_status = AccountStatus.LOCKED
    user.locked_until = utcnow() - timedelta(seconds=1)
    db.session.commit()
    assert login().status_code == 200
    db.session.refresh(user)
    assert user.account_status == AccountStatus.ACTIVE


def test_disabled_account_cannot_login(make_user, login):
    make_user(account_status=AccountStatus.DISABLED)
    assert login().status_code == 401


def test_me_requires_token(client):
    res = client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "AUTH_REQUIRED"


def test_me_returns_current_user(client, make_user, login):
    make_user(name="Asha")
    token = login().get_json()["access_token"]
    res = client.get("/api/v1/me", headers=auth_header(token))
    assert res.status_code == 200
    assert res.get_json()["user"]["name"] == "Asha"


def test_old_token_rejected_after_disable(client, make_user, login):
    user = make_user()
    token = login().get_json()["access_token"]
    user.account_status = AccountStatus.DISABLED
    db.session.commit()
    assert client.get("/api/v1/me", headers=auth_header(token)).status_code == 401


def test_lock_revokes_refresh_token(client, make_user, login):
    make_user()
    refresh = login().get_json()["refresh_token"]
    for _ in range(5):
        login(password="wrong")
    user = db.session.scalar(db.select(User).filter_by(login_id="student1"))
    user.account_status = AccountStatus.ACTIVE
    db.session.commit()
    res = client.post("/api/v1/auth/refresh", headers=auth_header(refresh))
    assert res.status_code == 401


def test_refresh_issues_new_access_token(client, make_user, login):
    make_user()
    refresh = login().get_json()["refresh_token"]
    res = client.post("/api/v1/auth/refresh", headers=auth_header(refresh))
    assert res.status_code == 200
    token = res.get_json()["access_token"]
    assert client.get("/api/v1/me", headers=auth_header(token)).status_code == 200


def test_access_token_cannot_refresh(client, make_user, login):
    make_user()
    access = login(password=PASSWORD).get_json()["access_token"]
    assert client.post("/api/v1/auth/refresh", headers=auth_header(access)).status_code == 401
