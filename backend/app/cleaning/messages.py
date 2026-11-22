from app.cleaning.models import CleaningRequest, TaskMessage
from app.cleaning.workflow import chat_access
from app.common.errors import clean_text, fail
from app.extensions import db
from app.notifications.service import notify
from app.users.models import Role, User

PREVIEW_LENGTH = 80


def list_messages(request: CleaningRequest, viewer: User) -> list[TaskMessage]:
    if chat_access(request, viewer) is None:
        raise fail("CHAT_NOT_OPEN")
    return request.messages


def post_message(request: CleaningRequest, sender: User, body) -> TaskMessage:
    access = chat_access(request, sender)
    if access is None:
        raise fail("CHAT_NOT_OPEN")
    if sender.role == Role.SUPER_ADMIN:
        raise fail("CHAT_READ_ONLY")
    if access != "send":
        raise fail("CHAT_CLOSED")
    text = clean_text(body, "body", "The message")
    if not text:
        raise fail("MESSAGE_REQUIRED", "body")
    message = TaskMessage(request=request, sender_id=sender.id, body=text)
    db.session.add(message)
    payload = {
        "request_id": request.id,
        "room": request.room_snapshot["number"],
        "sender": sender.name,
        "text": text if len(text) <= PREVIEW_LENGTH else f"{text[:PREVIEW_LENGTH]}…",
    }
    for user in (request.student, request.assigned_worker):
        if user is not None and user.id != sender.id:
            notify(user, "TASK_MESSAGE", payload)
    db.session.commit()
    return message
