import pytest

from app.common.audit import AuditLog, record_audit
from app.common.errors import ApiError
from app.common.settings import Setting, get_setting, set_setting
from app.extensions import db
from app.users.models import Role


def test_defaults_until_changed(app):
    assert get_setting("credit_cap") == 3
    assert get_setting("reschedule_hours") == 24


def test_setting_change_is_versioned_and_audited(make_user):
    admin = make_user(login_id="admin", role=Role.SUPER_ADMIN)
    set_setting("credit_cap", 4, admin, "More cleaning staff")
    set_setting("credit_cap", 2, admin, "Fewer staff")
    db.session.commit()

    assert get_setting("credit_cap") == 2
    versions = db.session.scalars(db.select(Setting.version).filter_by(key="credit_cap")).all()
    assert sorted(versions) == [1, 2]

    logs = db.session.scalars(db.select(AuditLog).order_by(AuditLog.id)).all()
    assert [log.action for log in logs] == ["SETTING_CHANGED", "SETTING_CHANGED"]
    assert logs[0].before_json == {"value": 3}
    assert logs[1].after_json == {"value": 2, "version": 2}
    assert logs[1].actor_id == admin.id
    assert logs[1].reason == "Fewer staff"


def test_setting_change_needs_reason_and_known_key(make_user):
    admin = make_user(login_id="admin", role=Role.SUPER_ADMIN)
    with pytest.raises(ApiError):
        set_setting("credit_cap", 4, admin, "")
    with pytest.raises(ApiError):
        set_setting("not_a_setting", 1, admin, "Reason")


def test_audit_entries_cannot_be_edited(app):
    entry = record_audit("TEST", "thing", 1)
    db.session.commit()
    entry.reason = "changed"
    with pytest.raises(RuntimeError):
        db.session.commit()
    db.session.rollback()


def test_grant_weekly_credits_command(app, make_user):
    make_user(login_id="stu", role=Role.STUDENT)
    runner = app.test_cli_runner()
    for date in ("2026-10-19", "2026-10-26", "2026-11-02", "2026-11-09"):
        result = runner.invoke(args=["grant-weekly-credits", "--date", date])
        assert result.exit_code == 0
    assert "0 granted, 1 at the limit" in result.output
