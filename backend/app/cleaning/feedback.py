from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.cleaning.models import CleaningRequest, Feedback
from app.cleaning.models import RequestStatus as S
from app.cleaning.workflow import feedback_deadline, feedback_state
from app.common.audit import record_audit
from app.common.errors import clean_text, fail
from app.common.models import utcnow
from app.common.time import day_clock
from app.extensions import db
from app.users.models import User


def submit_feedback(
    request: CleaningRequest, student: User, rating, comment, now: datetime | None = None
) -> CleaningRequest:
    state = feedback_state(request, now or utcnow())
    if state != "OPEN":
        raise fail(f"FEEDBACK_{state}")
    if type(rating) is not int or not 1 <= rating <= 5:
        raise fail("BAD_RATING", "rating")
    comment = clean_text(comment, "comment", "The comment")
    if rating <= 2 and not comment:
        raise fail("COMMENT_REQUIRED", "comment")
    db.session.add(
        Feedback(
            request=request,
            worker_id=request.assigned_worker_id,
            rating=rating,
            comment=comment,
        )
    )
    record_audit(
        "FEEDBACK_SUBMITTED",
        "cleaning_request",
        request.id,
        actor=student,
        after={"rating": rating},
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise fail("FEEDBACK_SUBMITTED") from None
    return request


def rating_due(student: User, now: datetime | None = None) -> dict | None:
    now = now or utcnow()
    last = db.session.scalar(
        db.select(CleaningRequest)
        .filter_by(student_id=student.id, status=S.CLOSED_SUCCESSFUL)
        .order_by(CleaningRequest.closed_at.desc(), CleaningRequest.id.desc())
    )
    if last is None or feedback_state(last, now) != "OPEN":
        return None
    return {
        "id": last.id,
        "room": last.room_snapshot["number"],
        "deadline_label": f"Rate by {day_clock(feedback_deadline(last))}",
    }


def rating_summary(worker_id: int) -> dict:
    count, average = db.session.execute(
        db.select(db.func.count(Feedback.id), db.func.avg(Feedback.rating)).filter_by(
            worker_id=worker_id
        )
    ).one()
    return {"count": count, "average": round(float(average), 1) if count else None}


def worker_feedback(worker: User) -> dict:
    comments = db.session.scalars(
        db.select(Feedback.comment)
        .filter(Feedback.worker_id == worker.id, Feedback.comment.is_not(None))
        .order_by(Feedback.comment)
    )
    return {**rating_summary(worker.id), "comments": list(comments)}
