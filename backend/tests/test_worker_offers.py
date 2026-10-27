from datetime import datetime, timedelta, timezone

import pytest

from app.cleaning.models import AssignmentOffer, OfferStatus, RequestStatus
from app.cleaning.recommendations import recommend, tier
from app.cleaning.service import (
    accept_offer,
    approve_request,
    cancel_by_student,
    decline_offer,
    offer_request,
    request_dict,
    submit_request,
    time_out_offers,
)
from app.cleaning.timers import _state, run_due
from app.common.audit import AuditLog
from app.common.errors import ApiError
from app.common.models import as_utc
from app.credits.service import grant_weekly_credit
from app.extensions import db
from app.hostel_structure.service import find_location, find_room
from app.notifications.models import Notification
from app.users.models import Role, StudentProfile, WorkerAvailability, WorkerProfile
from app.workers.service import (
    correct_location,
    remind_stale_locations,
    update_location,
    worker_dict,
)

NOW = datetime(2026, 10, 22, 4, 30, tzinfo=timezone.utc)
S = RequestStatus


@pytest.fixture
def boss(make_user):
    return make_user(login_id="sup", role=Role.SUPERVISOR, name="Sup")


@pytest.fixture
def make_worker(make_user, hostel):
    def _make(login_id, floor=None, wing="A", availability="AVAILABLE", minutes_ago=0):
        worker = make_user(login_id=login_id, role=Role.WORKER, name=login_id.title())
        worker.worker_profile = WorkerProfile(
            employee_id=login_id, availability=WorkerAvailability(availability)
        )
        db.session.commit()
        if floor is not None:
            update_location(
                worker, find_location(floor, wing).id, NOW - timedelta(minutes=minutes_ago)
            )
        return worker

    return _make


@pytest.fixture
def approved(resident, boss):
    grant_weekly_credit(resident, NOW)
    db.session.commit()
    request = submit_request(resident, availability_mode="ANY_TIME_TODAY", now=NOW)[0]
    return approve_request(request, boss)


def error_of(fn, *args, **kwargs):
    with pytest.raises(ApiError) as err:
        fn(*args, **kwargs)
    return err.value


@pytest.mark.parametrize(
    "floor, minutes_ago, freshness",
    [(None, 0, "UNKNOWN"), (1, 0, "FRESH"), (1, 29, "FRESH"), (1, 30, "STALE"), (2, 90, "STALE")],
)
def test_location_freshness(make_worker, floor, minutes_ago, freshness):
    worker = make_worker("w1", floor, minutes_ago=minutes_ago)
    assert worker_dict(worker, NOW)["freshness"] == freshness


def test_update_location_keeps_availability_and_audits(make_worker):
    worker = make_worker("w1", 2, wing="B", availability="BUSY")
    data = worker_dict(worker, NOW)
    assert (data["last_location"]["label"], data["availability"]) == ("Floor 2, Wing B", "BUSY")
    audit = db.session.scalar(db.select(AuditLog).filter_by(action="LOCATION_UPDATED"))
    assert (audit.actor_id, audit.after_json) == (worker.id, {"location": "Floor 2, Wing B"})


@pytest.mark.parametrize("location_id", [None, "1", 9999])
def test_update_location_rejects_bad_location(make_worker, location_id):
    assert error_of(update_location, make_worker("w1"), location_id).code == "INVALID_LOCATION"


def test_correct_location_needs_reason_and_records_it(make_worker, boss):
    worker = make_worker("w1", 1)
    spot = find_location(2, "A").id
    assert error_of(correct_location, worker.id, boss, spot, "  ").code == "REASON_REQUIRED"
    assert error_of(correct_location, boss.id, boss, spot, "x").code == "WORKER_NOT_FOUND"
    correct_location(worker.id, boss, spot, "Saw him upstairs")
    audit = db.session.scalar(db.select(AuditLog).filter_by(action="LOCATION_CORRECTED"))
    assert (audit.actor_id, audit.before_json["location"], audit.reason) == (
        boss.id,
        "Floor 1, Wing A",
        "Saw him upstairs",
    )


@pytest.mark.parametrize(
    "availability, distance, minutes, rank",
    [
        ("AVAILABLE", 0, 0, 1),
        ("BUSY", 0, 10, 2),
        ("BUSY", 0, 11, 5),
        ("AVAILABLE", 1, 0, 3),
        ("AVAILABLE", 2, 0, 3),
        ("AVAILABLE", 3, 0, 4),
        ("AVAILABLE", None, 0, 4),
        ("BUSY", 2, 40, 5),
        ("BUSY", 3, 0, None),
        ("BUSY", None, 0, None),
        ("OFF_DUTY", 0, 0, None),
    ],
)
def test_tier_order(availability, distance, minutes, rank):
    assert tier(availability, distance, minutes) == rank


def test_recommend_orders_tiers_with_reasons_and_warnings(approved, make_worker, make_user):
    make_worker("unknown")
    make_worker("near", 2)
    make_worker("off", 1, availability="OFF_DUTY")
    make_worker("same", 1, minutes_ago=45)
    busy = make_worker("busy", 1, availability="BUSY")
    student = make_user(login_id="upstairs", phone="+91 90000 22222")
    student.student_profile = StudentProfile(roll_number="24B0201", room=find_room("A201"))
    task = submit_request(student, "AVAILABLE_NOW", priority="URGENT", urgent_reason="x", now=NOW)[
        0
    ]
    task.status, task.assigned_worker = S.ACCEPTED_QUEUED, busy
    task.accepted_at, task.latest_eta_minutes = NOW - timedelta(minutes=5), 10
    picks = recommend(approved, NOW)
    assert [p["worker"]["name"] for p in picks] == ["Same", "Busy", "Near", "Unknown"]
    assert [p["tier"] for p in picks] == [1, 2, 3, 4]
    assert picks[0]["reason"] == "Available on the same floor (Floor 1, Wing A)."
    assert picks[0]["warnings"] == ["Location is 45 min old. Call to confirm where they are."]
    assert picks[1]["reason"] == "Busy on the same floor (Floor 1, Wing A), free in about 5 min."
    assert picks[1]["warnings"] == ["Already has 1 accepted task(s), about 5 min of work left."]
    assert picks[1]["worker"]["tasks"] == [
        {"id": task.id, "room": "A201", "status": "Worker accepted"}
    ]
    assert picks[2]["reason"] == "Available, 1 floor away (Floor 2, Wing A)."
    assert picks[3]["reason"] == "Available, location not known."


def test_offer_creates_pending_offer_and_notifies(approved, boss, make_worker):
    worker = make_worker("w1", 1)
    offer_request(approved, boss, worker.id, approved.lock_version, NOW)
    offer = db.session.scalar(db.select(AssignmentOffer))
    assert (approved.status, approved.assigned_worker_id) == (S.OFFERED, worker.id)
    assert (offer.status, offer.offered_by_id) == (OfferStatus.PENDING, boss.id)
    assert as_utc(offer.response_deadline) == NOW + timedelta(minutes=5)
    assert offer.explanation == "Available on the same floor (Floor 1, Wing A)."
    note = db.session.scalar(db.select(Notification).filter_by(user_id=worker.id))
    assert (note.type, note.payload_json["minutes"]) == ("OFFER_RECEIVED", 5)
    assert db.session.scalar(db.select(AuditLog).filter_by(action="OFFER_CREATED")) is not None
    assert approved.events[-1].event_type == "OFFERED"


def test_offer_is_idempotent_and_single(approved, boss, make_worker):
    first, second = make_worker("w1", 1), make_worker("w2", 1)
    version = approved.lock_version
    offer_request(approved, boss, first.id, version, NOW)
    assert offer_request(approved, boss, first.id, version, NOW).status == S.OFFERED
    assert error_of(offer_request, approved, boss, second.id, version, NOW).code == "CANNOT_OFFER"
    assert db.session.scalar(db.select(db.func.count(AssignmentOffer.id))) == 1


@pytest.mark.parametrize(
    "who, version_shift, lock, code",
    [
        ("w1", 0, "1", "INVALID_FIELD"),
        ("w1", 1, None, "STALE_REQUEST"),
        ("off", 0, None, "WORKER_OFF_DUTY"),
        ("sup", 0, None, "WORKER_NOT_FOUND"),
    ],
)
def test_offer_rules(approved, boss, make_worker, who, version_shift, lock, code):
    make_worker("w1", 1)
    make_worker("off", 1, availability="OFF_DUTY")
    target = db.session.scalar(db.select(type(boss)).filter_by(login_id=who))
    version = lock if lock is not None else approved.lock_version + version_shift
    assert error_of(offer_request, approved, boss, target.id, version, NOW).code == code


def test_offer_needs_approval_first(resident, boss, make_worker):
    grant_weekly_credit(resident, NOW)
    db.session.commit()
    request = submit_request(resident, "ANY_TIME_TODAY", now=NOW)[0]
    worker = make_worker("w1", 1)
    code = error_of(offer_request, request, boss, worker.id, request.lock_version, NOW).code
    assert code == "CANNOT_OFFER"


def test_manual_pick_outside_recommendations(approved, boss, make_worker):
    worker = make_worker("w1", availability="BUSY")
    offer_request(approved, boss, worker.id, approved.lock_version, NOW)
    assert approved.offers[0].explanation == "Chosen by the supervisor from the full list."


def test_student_cancel_withdraws_offer(approved, boss, make_worker, resident):
    worker = make_worker("w1", 1)
    offer_request(approved, boss, worker.id, approved.lock_version, NOW)
    cancel_by_student(approved, resident)
    assert approved.offers[0].status == OfferStatus.WITHDRAWN
    types = db.session.scalars(db.select(Notification.type).filter_by(user_id=worker.id)).all()
    assert types == ["OFFER_RECEIVED", "REQUEST_CANCELLED_BY_STUDENT"]


def headers(login, login_id):
    return {"Authorization": f"Bearer {login(login_id).get_json()['access_token']}"}


def test_worker_and_location_api(client, login, boss, make_worker, resident):
    worker = make_worker("w1")
    spot = find_location(1, "B").id
    sup, own, student = headers(login, "sup"), headers(login, "w1"), headers(login, "resident")
    url = "/api/v1/workers"
    assert client.get(url, headers=student).status_code == 403
    assert client.get(url, headers=own).status_code == 403
    res = client.patch(f"{url}/me/location", json={"location_id": spot}, headers=own)
    assert res.get_json()["worker"]["freshness"] == "FRESH"
    assert client.patch(f"{url}/me/location", json={}, headers=sup).status_code == 403
    me = client.get("/api/v1/me", headers=own).get_json()["profile"]
    assert (me["last_location"]["label"], me["freshness"]) == ("Floor 1, Wing B", "FRESH")
    body = {"location_id": spot}
    assert client.patch(f"{url}/{worker.id}/location", json=body, headers=sup).status_code == 400
    body["reason"] = "Phoned him"
    assert client.patch(f"{url}/{worker.id}/location", json=body, headers=sup).status_code == 200
    names = [w["name"] for w in client.get(url, headers=sup).get_json()["workers"]]
    assert names == ["W1"]


def test_recommend_and_offer_api(client, login, approved, make_worker):
    worker = make_worker("w1", 1)
    sup, own = headers(login, "sup"), headers(login, "w1")
    url = f"/api/v1/cleaning/requests/{approved.id}"
    assert client.get(f"{url}/recommendations", headers=own).status_code == 403
    picks = client.get(f"{url}/recommendations", headers=sup).get_json()["recommendations"]
    assert [p["worker"]["id"] for p in picks] == [worker.id]
    seen = client.get(url, headers=sup).get_json()["request"]
    assert seen["actions"] == ["change", "offer"] and seen["offer"] is None
    body = {"worker_id": worker.id, "lock_version": seen["lock_version"]}
    res = client.post(f"{url}/offers", json=body, headers=sup)
    data = res.get_json()["request"]
    assert (res.status_code, data["status"], data["actions"]) == (201, "OFFERED", [])
    assert data["offer"]["worker"]["name"] == "W1" and data["offer"]["status"] == "PENDING"
    assert data["offer"]["summary"].startswith("Offered to W1 until ")
    assert client.get(url, headers=own).get_json()["request"]["status"] == "OFFERED"


@pytest.fixture
def offered(approved, boss, make_worker):
    worker = make_worker("w1", 1)
    offer_request(approved, boss, worker.id, approved.lock_version, NOW)
    return approved.offers[0]


def later(minutes):
    return NOW + timedelta(minutes=minutes)


def test_accept_queues_request_and_notifies(offered, boss, resident):
    worker, request = offered.worker, offered.request
    accept_offer(offered, worker, 15, later(1))
    assert (request.status, offered.status) == (S.ACCEPTED_QUEUED, OfferStatus.ACCEPTED)
    assert (request.original_eta_minutes, request.latest_eta_minutes) == (15, 15)
    assert worker.worker_profile.availability == WorkerAvailability.BUSY
    assert request.events[-1].event_type == "ACCEPTED"
    assert request_dict(request, resident)["eta_label"] == "W1, expected by 10:16 am"
    notes = db.session.scalars(db.select(Notification).filter_by(type="OFFER_ACCEPTED")).all()
    assert {(n.user_id, n.payload_json["eta"]) for n in notes} == {(resident.id, 15), (boss.id, 15)}
    assert accept_offer(offered, worker, 30, later(2)).latest_eta_minutes == 15


@pytest.mark.parametrize("eta", [0, 3, 125, "15", None, True, 7.5])
def test_accept_needs_eta_in_steps_of_five(offered, eta):
    assert error_of(accept_offer, offered, offered.worker, eta, later(1)).code == "INVALID_ETA"


def test_answer_only_while_open(offered, resident):
    assert error_of(accept_offer, offered, offered.worker, 15, later(5)).code == "OFFER_EXPIRED"
    cancel_by_student(offered.request, resident)
    assert error_of(decline_offer, offered, offered.worker, "x", later(1)).code == "OFFER_CLOSED"


def test_decline_reopens_and_skips_worker(offered, boss, make_worker):
    worker, request = offered.worker, offered.request
    other = make_worker("w2", 1)
    assert error_of(decline_offer, offered, worker, " ", later(1)).code == "REASON_REQUIRED"
    decline_offer(offered, worker, "Too far", later(1))
    assert (request.status, request.assigned_worker) == (S.AWAITING_REASSIGNMENT, None)
    assert (offered.status, offered.decline_reason) == (OfferStatus.DECLINED, "Too far")
    note = db.session.scalar(db.select(Notification).filter_by(type="OFFER_DECLINED"))
    assert (note.user_id, note.payload_json["reason"]) == (boss.id, "Too far")
    assert [p["worker"]["id"] for p in recommend(request, later(1))] == [other.id]
    offer_request(request, boss, worker.id, request.lock_version, later(2))
    assert request.offers[-1].explanation == "Chosen by the supervisor from the full list."


def test_timeout_is_safe_to_run_twice(offered, boss):
    request = offered.request
    assert time_out_offers(later(4)) == 0
    assert (time_out_offers(later(5)), time_out_offers(later(6))) == (1, 0)
    assert (request.status, offered.status) == (S.AWAITING_REASSIGNMENT, OfferStatus.TIMED_OUT)
    assert request.events[-1].payload_json["reason"] == "NO_RESPONSE"
    assert db.session.scalar(db.select(Notification).filter_by(type="OFFER_TIMED_OUT")) is not None
    assert recommend(request, later(6)) == []


def test_accepted_offer_never_times_out_and_cancel_frees_worker(offered, resident):
    worker = offered.worker
    accept_offer(offered, worker, 10, later(1))
    assert time_out_offers(later(30)) == 0
    assert worker_dict(worker, later(2))["tasks"][0]["status"] == "Worker accepted"
    cancel_by_student(offered.request, resident)
    assert worker.worker_profile.availability == WorkerAvailability.AVAILABLE


def test_timers_grant_weekly_credit_once(app, offered, resident):
    _state["week"] = None
    first, second = run_due(later(10)), run_due(later(11))
    credits = {"granted": 0, "capped": 0, "already": 1}
    assert first == {"offers_timed_out": 1, "locations_reminded": 0, "weekly_credits": credits}
    assert second["weekly_credits"] is None
    output = app.test_cli_runner().invoke(args=["run-timers"]).output
    assert "Offers timed out: 0" in output and "Weekly credits: " in output


def test_stale_location_reminder_is_sent_once(make_worker):
    worker = make_worker("w1", 1, minutes_ago=45)
    make_worker("off", 1, availability="OFF_DUTY", minutes_ago=45)
    make_worker("fresh", 1)
    make_worker("never")
    assert (remind_stale_locations(NOW), remind_stale_locations(NOW)) == (1, 0)
    note = db.session.scalar(db.select(Notification).filter_by(type="LOCATION_STALE"))
    assert (note.user_id, note.payload_json) == (worker.id, {"minutes": 45})
    soon = datetime.now(timezone.utc) + timedelta(hours=1)
    update_location(worker, find_location(2, "A").id, soon)
    assert remind_stale_locations(soon + timedelta(hours=1)) == 2


def test_offer_response_api(client, login, approved, make_worker, resident):
    worker = make_worker("w1", 1)
    make_worker("w2", 1)
    sup, own, other = headers(login, "sup"), headers(login, "w1"), headers(login, "w2")
    body = {"worker_id": worker.id, "lock_version": approved.lock_version}
    client.post(f"/api/v1/cleaning/requests/{approved.id}/offers", json=body, headers=sup)
    url = "/api/v1/worker/offers"
    assert client.get(url, headers=sup).status_code == 403
    listed = client.get(url, headers=own).get_json()["offers"]
    assert [o["request"]["contact_phone"] for o in listed] == ["+91 90000 11111"]
    accept = f"{url}/{listed[0]['id']}/accept"
    assert client.post(accept, json={"eta_minutes": 20}, headers=other).status_code == 404
    assert client.post(f"{url}/{listed[0]['id']}/decline", json={}, headers=own).status_code == 400
    res = client.post(accept, json={"eta_minutes": 20}, headers=own)
    assert res.get_json()["request"]["status"] == "ACCEPTED_QUEUED"
    assert client.get(url, headers=own).get_json()["offers"] == []
    mine = client.get(
        f"/api/v1/cleaning/requests/{approved.id}", headers=headers(login, "resident")
    )
    assert mine.get_json()["request"]["eta_label"].startswith("W1, expected by ")
    tasks = client.get("/api/v1/me", headers=own).get_json()["profile"]["tasks"]
    assert [t["room"] for t in tasks] == ["A102"]
