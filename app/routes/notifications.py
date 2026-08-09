from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Notification, User
from app.schemas import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def serialize(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        post_id=row.post_id,
        is_read=row.is_read,
        created_at=row.created_at,
        actor_id=row.actor_id,
        actor_username=row.actor.username,
        actor_full_name=row.actor.full_name,
        actor_profile_image=row.actor.profile_image,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == current.id)
        .order_by(Notification.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    return [serialize(row) for row in rows]


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current.id,
            Notification.is_read.is_(False),
        )
        .count()
    )
    return {"unread_count": count}


@router.post("/read-all")
def read_all(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current.id,
        Notification.is_read.is_(False),
    ).update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"message": "All notifications marked as read"}


@router.post("/{notification_id}/read")
def read_one(
    notification_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    row = db.get(Notification, notification_id)
    if not row or row.user_id != current.id:
        raise HTTPException(404, "Notification not found")
    row.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}
