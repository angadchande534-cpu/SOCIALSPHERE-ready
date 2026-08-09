from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.media import delete_local_upload, save_upload
from app.models import Story, StoryView, User, now_utc
from app.schemas import StoryOut

router = APIRouter(prefix="/api/stories", tags=["Stories"])
BASE_DIR = Path(__file__).resolve().parents[2]
STORY_DIR = BASE_DIR / "uploads" / "stories"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def cleanup_expired(db: Session) -> None:
    expired = db.query(Story).filter(Story.expires_at <= now_utc()).all()
    if not expired:
        return
    urls = [story.media_url for story in expired]
    for story in expired:
        db.delete(story)
    db.commit()
    for url in urls:
        delete_local_upload(BASE_DIR, url)


def serialize(story: Story, db: Session, current_id: int) -> StoryOut:
    return StoryOut(
        id=story.id,
        user_id=story.user_id,
        username=story.author.username,
        full_name=story.author.full_name,
        profile_image=story.author.profile_image,
        media_url=story.media_url,
        media_type=story.media_type,
        caption=story.caption,
        created_at=_aware(story.created_at),
        expires_at=_aware(story.expires_at),
        views_count=db.query(StoryView).filter(StoryView.story_id == story.id).count(),
        viewed_by_me=db.query(StoryView).filter(
            StoryView.story_id == story.id,
            StoryView.user_id == current_id,
        ).first() is not None,
        is_mine=story.user_id == current_id,
    )


@router.post("", response_model=StoryOut, status_code=201)
def create_story(
    caption: str = Form(""),
    media: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    media_url, media_type = save_upload(
        media,
        STORY_DIR,
        "/uploads/stories",
        max_bytes=60 * 1024 * 1024,
    )
    story = Story(
        user_id=current.id,
        media_url=media_url,
        media_type=media_type,
        caption=caption.strip() or None,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return serialize(story, db, current.id)


@router.get("", response_model=list[StoryOut])
def active_stories(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    cleanup_expired(db)
    stories = (
        db.query(Story)
        .filter(Story.expires_at > now_utc())
        .order_by(Story.created_at.desc())
        .all()
    )
    return [serialize(story, db, current.id) for story in stories]


@router.post("/{story_id}/view")
def mark_viewed(
    story_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    story = db.get(Story, story_id)
    if not story or _aware(story.expires_at) <= now_utc():
        raise HTTPException(404, "Story not found or expired")

    if story.user_id != current.id:
        existing = db.query(StoryView).filter(
            StoryView.story_id == story_id,
            StoryView.user_id == current.id,
        ).first()
        if not existing:
            db.add(StoryView(story_id=story_id, user_id=current.id))
            db.commit()

    return {
        "views_count": db.query(StoryView).filter(StoryView.story_id == story_id).count()
    }


@router.delete("/{story_id}")
def delete_story(
    story_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    if story.user_id != current.id:
        raise HTTPException(403, "You can only delete your own story")

    media_url = story.media_url
    db.delete(story)
    db.commit()
    delete_local_upload(BASE_DIR, media_url)
    return {"message": "Story deleted"}
