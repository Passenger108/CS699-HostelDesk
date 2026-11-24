from datetime import datetime, timedelta

from app.cleaning.arrival import _payload, _save, _step
from app.cleaning.models import CleaningRequest, CreditReservation, ProofPhoto
from app.cleaning.models import RequestStatus as S
from app.cleaning.service import _free_worker, release
from app.cleaning.workflow import latest_proof, record_event, stale, sweep, transition
from app.common.audit import record_audit
from app.common.errors import clean_text, fail
from app.common.models import as_utc, utcnow
from app.common.storage import read_image, save, stamp
from app.common.time import clock, day_clock, hostel_now
from app.credits.service import consume_credit, grant_goodwill
from app.extensions import db
from app.hostel_structure.service import find_location
from app.notifications.service import notify, notify_supervisors
from app.users.models import User

CHECKLIST = ("swept", "mopped", "balcony_cleaned", "fan_cleaned")
CONFIRM_MINUTES = 2
OUTCOMES = {
    "valid": (S.CLOSED_VALID_AFTER_REVIEW, "the cleaning was valid"),
    "unsatisfactory": (S.CLOSED_UNSATISFACTORY, "the cleaning was unsatisfactory"),
}


def add_proof(request: CleaningRequest, worker: User, upload, now: datetime | None = None):
    now = now or utcnow()
    _step(request, S.CLEANING_IN_PROGRESS)
    image = read_image(upload)
    room, local = request.room_snapshot, hostel_now(now)
    data = stamp(
        image,
        [
            f"HostelDesk request {request.id}",
            f"Room {room['number']}, {room['floor_label']}, Wing {room['wing']}",
            f"{local:%d %b %Y}, {clock(now)} server time",
        ],
    )
    key = save(data)
    db.session.add(
        ProofPhoto(
            request=request,
            uploaded_by_id=worker.id,
            storage_key=key,
            content_type="image/jpeg",
            size_bytes=len(data),
        )
    )
    record_event(request, "PROOF_ADDED", worker, request.status)
    record_audit("PROOF_ADDED", "cleaning_request", request.id, actor=worker, after={"key": key})
    db.session.commit()
    return request


def _checklist(value) -> dict:
    if (
        type(value) is not dict
        or set(value) != set(CHECKLIST)
        or any(type(ticked) is not bool for ticked in value.values())
    ):
        raise fail("BAD_CHECKLIST", "checklist")
    if not all(value.values()):
        raise fail("CHECKLIST_INCOMPLETE", "checklist")
    return value


def complete(request: CleaningRequest, worker: User, checklist, now: datetime | None = None):
    now = now or utcnow()
    if request.status == S.AWAITING_STUDENT_CONFIRMATION:
        return request
    checklist = _checklist(checklist)
    _step(request, S.CLEANING_IN_PROGRESS)
    if latest_proof(request) is None:
        raise fail("NO_PROOF")
    location = find_location(request.room_snapshot["floor"], request.room_snapshot["wing"])

    def work():
        request.checklist = checklist
        request.confirm_deadline = now + timedelta(minutes=CONFIRM_MINUTES)
        transition(request, S.AWAITING_STUDENT_CONFIRMATION, worker, "COMPLETED")
        if location is not None:
            worker.worker_profile.last_location = location
            worker.worker_profile.location_updated_at = now
        _free_worker(worker)
        record_audit(
            "CLEANING_COMPLETED", "cleaning_request", request.id, actor=worker, after=checklist
        )
        payload = _payload(request, worker=worker.name, time=clock(request.confirm_deadline))
        notify(request.student, "WORK_DONE", payload)
        notify_supervisors("WORK_DONE", payload)

    return _save(request, lambda latest: latest.status == S.AWAITING_STUDENT_CONFIRMATION, work)


def _consume(request: CleaningRequest, reason: str, actor: User | None) -> None:
    if request.credit_reservation == CreditReservation.RESERVED:
        consume_credit(request.student, request.id, reason, actor=actor)
        request.credit_reservation = CreditReservation.CONSUMED


def _answerable(request: CleaningRequest, now: datetime) -> None:
    _step(request, S.AWAITING_STUDENT_CONFIRMATION)
    if as_utc(request.confirm_deadline) <= now:
        raise fail("CONFIRM_CLOSED")


def _close(request: CleaningRequest, student: User | None):
    event = "CONFIRMED" if student else "AUTO_CONFIRMED"

    def work():
        _consume(request, "Cleaning confirmed" if student else "Closed as cleaned", student)
        transition(request, S.CLOSED_SUCCESSFUL, student, event)
        record_audit(event, "cleaning_request", request.id, actor=student)
        payload = _payload(request)
        notify(request.assigned_worker, "CLEANING_CONFIRMED", payload)
        if student is None:
            notify(request.student, "AUTO_CONFIRMED", payload)

    return _save(request, lambda latest: latest.status == S.CLOSED_SUCCESSFUL, work)


def confirm(request: CleaningRequest, student: User, now: datetime | None = None):
    if request.status == S.CLOSED_SUCCESSFUL:
        return request
    _answerable(request, now or utcnow())
    return _close(request, student)


def close_unconfirmed(now: datetime | None = None) -> int:
    now = now or utcnow()
    waiting = db.select(CleaningRequest).filter_by(status=S.AWAITING_STUDENT_CONFIRMATION)
    return sweep(
        waiting, lambda request: as_utc(request.confirm_deadline) <= now and _close(request, None)
    )


def dispute(request: CleaningRequest, student: User, reason, now: datetime | None = None):
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("DISPUTE_REASON", "reason")
    if request.status == S.DISPUTED:
        return request
    _answerable(request, now or utcnow())

    def work():
        transition(request, S.DISPUTED, student, payload={"reason": reason})
        record_audit(
            "CLEANING_DISPUTED", "cleaning_request", request.id, actor=student, reason=reason
        )
        payload = _payload(request, reason=reason)
        notify_supervisors("CLEANING_DISPUTED", payload)
        notify(request.assigned_worker, "CLEANING_DISPUTED", payload)

    return _save(request, lambda latest: latest.status == S.DISPUTED, work)


def resolve_dispute(
    request: CleaningRequest,
    supervisor: User,
    outcome,
    reason,
    lock_version,
    goodwill=False,
    now: datetime | None = None,
):
    now = now or utcnow()
    reason = clean_text(reason, "reason", "The reason")
    if not reason:
        raise fail("RESOLVE_REASON", "reason")
    if outcome not in OUTCOMES:
        raise fail("BAD_OUTCOME", "outcome")
    if goodwill is True and outcome != "unsatisfactory":
        raise fail("GOODWILL_ONLY_UNSATISFACTORY", "goodwill")
    if type(lock_version) is not int:
        raise fail("BAD_LOCK_VERSION", "lock_version")
    target, verdict = OUTCOMES[outcome]
    if request.status == target:
        return request
    _step(request, S.DISPUTED)
    if lock_version != request.lock_version:
        raise stale(request.id)

    def work():
        if outcome == "valid":
            _consume(request, "Dispute decided: the cleaning was valid", supervisor)
        else:
            release(request, "Dispute decided: the cleaning was unsatisfactory", supervisor)
        request.resolution_reason = reason
        transition(
            request,
            target,
            supervisor,
            f"DISPUTE_{outcome.upper()}",
            {"reason": reason, "goodwill": goodwill is True},
        )
        record_audit(
            f"DISPUTE_{outcome.upper()}",
            "cleaning_request",
            request.id,
            actor=supervisor,
            after={"status": target.value, "goodwill": goodwill is True},
            reason=reason,
        )
        payload = _payload(request, outcome=verdict, reason=reason)
        for user in (request.student, request.assigned_worker):
            notify(user, "DISPUTE_RESOLVED", payload)
        if goodwill is True:
            entry = grant_goodwill(request.student, supervisor, reason, now)
            notify(
                request.student,
                "GOODWILL_GRANTED",
                _payload(request, time=day_clock(entry.expires_at)),
            )

    return _save(request, lambda latest: latest.status == target, work)
