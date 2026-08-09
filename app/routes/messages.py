from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.media import delete_local_upload, save_upload
from app.models import Message, MessageAttachment, Notification, User, now_utc
from app.schemas import ConversationOut, MessageCreate, MessageOut

router = APIRouter(prefix="/api/messages", tags=["Messages"])
BASE_DIR = Path(__file__).resolve().parents[2]
MESSAGE_DIR = BASE_DIR / "uploads" / "messages"


def serialize_message(message: Message, db: Session) -> MessageOut:
    attachment = message.attachment or db.query(MessageAttachment).filter(
        MessageAttachment.message_id == message.id
    ).first()
    return MessageOut(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        text=message.text,
        media_url=attachment.media_url if attachment else None,
        media_type=attachment.media_type if attachment else None,
        duration_seconds=attachment.duration_seconds if attachment else None,
        is_read=message.is_read,
        created_at=message.created_at,
    )


def touch_message_notification(db: Session, *, recipient_id: int, sender_id: int) -> None:
    existing = db.query(Notification).filter(
        Notification.user_id == recipient_id,
        Notification.actor_id == sender_id,
        Notification.kind == "message",
        Notification.post_id.is_(None),
    ).first()
    if existing:
        existing.is_read = False
        existing.created_at = now_utc()
    else:
        db.add(Notification(user_id=recipient_id, actor_id=sender_id, kind="message", post_id=None))


def ensure_recipient(db: Session, current: User, user_id: int) -> User:
    if user_id == current.id:
        raise HTTPException(400, "You cannot message yourself")
    recipient = db.get(User, user_id)
    if not recipient:
        raise HTTPException(404, "User not found")
    return recipient


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    rows = db.query(Message).filter(
        or_(Message.sender_id == current.id, Message.recipient_id == current.id)
    ).order_by(Message.created_at.desc(), Message.id.desc()).all()

    latest_by_user: dict[int, Message] = {}
    for row in rows:
        other_id = row.recipient_id if row.sender_id == current.id else row.sender_id
        latest_by_user.setdefault(other_id, row)

    result: list[ConversationOut] = []
    for other_id, latest in latest_by_user.items():
        other = db.get(User, other_id)
        if not other:
            continue
        unread = db.query(Message).filter(
            Message.sender_id == other_id,
            Message.recipient_id == current.id,
            Message.is_read.is_(False),
        ).count()
        attachment = latest.attachment or db.query(MessageAttachment).filter(
            MessageAttachment.message_id == latest.id
        ).first()
        preview = latest.text.strip()
        if not preview and attachment:
            preview = {"image":"Photo", "video":"Video", "audio":"Voice message"}.get(attachment.media_type, "Attachment")
        result.append(ConversationOut(
            user_id=other.id,
            username=other.username,
            full_name=other.full_name,
            profile_image=other.profile_image,
            last_message=preview or "Message",
            last_message_at=latest.created_at,
            last_message_sent_by_me=latest.sender_id == current.id,
            unread_count=unread,
        ))

    result.sort(key=lambda item: item.last_message_at, reverse=True)
    return result


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    count = db.query(Message).filter(
        Message.recipient_id == current.id,
        Message.is_read.is_(False),
    ).count()
    return {"unread_count": count}


@router.get("/users/{user_id}", response_model=list[MessageOut])
def conversation_messages(
    user_id: int,
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if user_id == current.id:
        raise HTTPException(400, "Choose another user to start a conversation")
    if not db.get(User, user_id):
        raise HTTPException(404, "User not found")

    rows = db.query(Message).filter(
        or_(
            and_(Message.sender_id == current.id, Message.recipient_id == user_id),
            and_(Message.sender_id == user_id, Message.recipient_id == current.id),
        )
    ).order_by(Message.created_at.desc(), Message.id.desc()).limit(limit).all()
    rows.reverse()

    unread_rows = [
        row for row in rows
        if row.sender_id == user_id and row.recipient_id == current.id and not row.is_read
    ]
    for row in unread_rows:
        row.is_read = True

    notification = db.query(Notification).filter(
        Notification.user_id == current.id,
        Notification.actor_id == user_id,
        Notification.kind == "message",
        Notification.post_id.is_(None),
    ).first()
    if notification:
        notification.is_read = True
    if unread_rows or notification:
        db.commit()

    return [serialize_message(row, db) for row in rows]


@router.post("/users/{user_id}", response_model=MessageOut, status_code=201)
def send_message(
    user_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    recipient = ensure_recipient(db, current, user_id)
    text = data.text.strip()
    if not text:
        raise HTTPException(400, "Message cannot be empty")

    message = Message(sender_id=current.id, recipient_id=recipient.id, text=text)
    db.add(message)
    touch_message_notification(db, recipient_id=recipient.id, sender_id=current.id)
    db.commit()
    db.refresh(message)
    return serialize_message(message, db)


@router.post("/users/{user_id}/media", response_model=MessageOut, status_code=201)
def send_media_message(
    user_id: int,
    text: str = Form(""),
    media: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    recipient = ensure_recipient(db, current, user_id)
    media_url, media_type = save_upload(
        media,
        MESSAGE_DIR,
        "/uploads/messages",
        max_bytes=60 * 1024 * 1024,
    )
    message = Message(sender_id=current.id, recipient_id=recipient.id, text=text.strip())
    db.add(message)
    db.flush()
    db.add(MessageAttachment(
        message_id=message.id,
        media_url=media_url,
        media_type=media_type,
    ))
    touch_message_notification(db, recipient_id=recipient.id, sender_id=current.id)
    db.commit()
    db.refresh(message)
    return serialize_message(message, db)


@router.post("/users/{user_id}/voice", response_model=MessageOut, status_code=201)
def send_voice_message(
    user_id: int,
    duration_seconds: float | None = Form(None),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    recipient = ensure_recipient(db, current, user_id)
    media_url, media_type = save_upload(
        audio, MESSAGE_DIR, "/uploads/messages", max_bytes=25 * 1024 * 1024, allowed_types={"audio"}
    )
    message = Message(sender_id=current.id, recipient_id=recipient.id, text="")
    db.add(message)
    db.flush()
    db.add(MessageAttachment(
        message_id=message.id, media_url=media_url, media_type=media_type, duration_seconds=duration_seconds
    ))
    touch_message_notification(db, recipient_id=recipient.id, sender_id=current.id)
    db.commit()
    db.refresh(message)
    return serialize_message(message, db)


@router.delete("/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(404, "Message not found")
    if message.sender_id != current.id:
        raise HTTPException(403, "You can only delete messages you sent")

    attachment = message.attachment or db.query(MessageAttachment).filter(
        MessageAttachment.message_id == message.id
    ).first()
    media_url = attachment.media_url if attachment else None
    db.delete(message)
    db.commit()
    delete_local_upload(BASE_DIR, media_url)
    return {"message": "Message deleted"}
