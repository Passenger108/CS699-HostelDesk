from app.credits.service import grant_weekly_credit
from app.users.models import Role


def test_student_sees_balance_and_history(make_user, auth_get):
    student = make_user(login_id="stu", role=Role.STUDENT)
    grant_weekly_credit(student)
    res = auth_get("/api/v1/me/credits", login_id="stu")
    assert res.status_code == 200
    body = res.get_json()
    assert body["balance"]["available"] == 1
    assert body["balance"]["reserved"] == 0
    assert body["balance"]["cap"] == 3
    assert body["balance"]["next_grant_at"]
    assert [row["entry_type"] for row in body["history"]] == ["WEEKLY_GRANT"]
    assert body["history"][0]["grant_week"]


def test_new_student_has_empty_ledger(make_user, auth_get):
    make_user(login_id="stu", role=Role.STUDENT)
    body = auth_get("/api/v1/me/credits", login_id="stu").get_json()
    assert body["balance"]["available"] == 0
    assert body["history"] == []


def test_only_students_have_credits(make_user, auth_get):
    make_user(login_id="sup", role=Role.SUPERVISOR)
    assert auth_get("/api/v1/me/credits", login_id="sup").status_code == 403


def test_credits_require_login(client):
    assert client.get("/api/v1/me/credits").status_code == 401
