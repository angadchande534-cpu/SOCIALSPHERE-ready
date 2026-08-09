from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.media import delete_local_upload, save_upload
from app.models import Reel, ReelComment, ReelLike, ReelView, User, now_utc
from app.schemas import ReelCommentCreate, ReelCommentOut, ReelOut

router = APIRouter(prefix="/api/reels", tags=["Reels"])
BASE_DIR = Path(__file__).resolve().parents[2]
REEL_DIR = BASE_DIR / "uploads" / "reels"
COVER_DIR = BASE_DIR / "uploads" / "covers"


def serialize(reel: Reel, db: Session, current_id: int) -> ReelOut:
    return ReelOut(
        id=reel.id,
        user_id=reel.user_id,
        username=reel.author.username,
        full_name=reel.author.full_name,
        profile_image=reel.author.profile_image,
        caption=reel.caption,
        video_url=reel.video_url,
        cover_url=reel.cover_url,
        audio_name=reel.audio_name,
        duration_seconds=reel.duration_seconds,
        width=reel.width,
        height=reel.height,
        quality_label=reel.quality_label,
        created_at=reel.created_at,
        likes_count=db.query(ReelLike).filter(ReelLike.reel_id == reel.id).count(),
        comments_count=db.query(ReelComment).filter(ReelComment.reel_id == reel.id).count(),
        views_count=db.query(ReelView).filter(ReelView.reel_id == reel.id).count(),
        liked_by_me=db.query(ReelLike).filter(ReelLike.reel_id == reel.id, ReelLike.user_id == current_id).first() is not None,
    )


@router.post("", response_model=ReelOut, status_code=201)
def create_reel(
    caption: str = Form(""),
    audio_name: str = Form("Original audio"),
    duration_seconds: float | None = Form(None),
    width: int | None = Form(None),
    height: int | None = Form(None),
    video: UploadFile = File(...),
    cover: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    video_url, media_type = save_upload(video, REEL_DIR, "/uploads/reels", max_bytes=250 * 1024 * 1024, allowed_types={"video"})
    if media_type != "video":
        raise HTTPException(400, "Reels must be video files")
    cover_url = None
    if cover and cover.filename:
        cover_url, _ = save_upload(cover, COVER_DIR, "/uploads/covers", max_bytes=10 * 1024 * 1024, allowed_types={"image"})
    quality = "HD"
    if height and height >= 1080:
        quality = "1080p"
    elif height and height >= 720:
        quality = "720p"
    reel = Reel(
        user_id=current.id,
        caption=caption.strip(),
        video_url=video_url,
        cover_url=cover_url,
        audio_name=(audio_name or "Original audio").strip()[:120],
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        quality_label=quality,
    )
    db.add(reel)
    db.commit()
    db.refresh(reel)
    return serialize(reel, db, current.id)


@router.get("", response_model=list[ReelOut])
def list_reels(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    rows = db.query(Reel).order_by(Reel.created_at.desc()).offset(skip).limit(limit).all()
    return [serialize(row, db, current.id) for row in rows]


@router.get("/mine", response_model=list[ReelOut])
def my_reels(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = db.query(Reel).filter(Reel.user_id == current.id).order_by(Reel.created_at.desc()).all()
    return [serialize(row, db, current.id) for row in rows]


@router.post("/{reel_id}/like")
def toggle_like(reel_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not db.get(Reel, reel_id):
        raise HTTPException(404, "Reel not found")
    row = db.query(ReelLike).filter(ReelLike.reel_id == reel_id, ReelLike.user_id == current.id).first()
    if row:
        db.delete(row); liked = False
    else:
        db.add(ReelLike(reel_id=reel_id, user_id=current.id)); liked = True
    db.commit()
    return {"liked": liked, "likes_count": db.query(ReelLike).filter(ReelLike.reel_id == reel_id).count()}


@router.post("/{reel_id}/view")
def register_view(reel_id: int, watched_seconds: float = 0, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not db.get(Reel, reel_id):
        raise HTTPException(404, "Reel not found")
    row = db.query(ReelView).filter(ReelView.reel_id == reel_id, ReelView.user_id == current.id).first()
    if row:
        row.watched_seconds = max(row.watched_seconds or 0, max(0, watched_seconds)); row.updated_at = now_utc()
    else:
        db.add(ReelView(reel_id=reel_id, user_id=current.id, watched_seconds=max(0, watched_seconds)))
    db.commit()
    return {"views_count": db.query(ReelView).filter(ReelView.reel_id == reel_id).count()}


@router.get("/{reel_id}/comments", response_model=list[ReelCommentOut])
def list_comments(reel_id: int, db: Session = Depends(get_db)):
    if not db.get(Reel, reel_id): raise HTTPException(404, "Reel not found")
    rows = db.query(ReelComment).filter(ReelComment.reel_id == reel_id).order_by(ReelComment.created_at.asc()).all()
    return [ReelCommentOut(id=r.id,text=r.text,created_at=r.created_at,user_id=r.user_id,username=r.author.username,profile_image=r.author.profile_image) for r in rows]


@router.post("/{reel_id}/comments", response_model=ReelCommentOut, status_code=201)
def add_comment(reel_id: int, data: ReelCommentCreate, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not db.get(Reel, reel_id): raise HTTPException(404, "Reel not found")
    row = ReelComment(reel_id=reel_id, user_id=current.id, text=data.text.strip())
    db.add(row); db.commit(); db.refresh(row)
    return ReelCommentOut(id=row.id,text=row.text,created_at=row.created_at,user_id=current.id,username=current.username,profile_image=current.profile_image)


@router.delete("/{reel_id}")
def delete_reel(reel_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    reel = db.get(Reel, reel_id)
    if not reel: raise HTTPException(404, "Reel not found")
    if reel.user_id != current.id: raise HTTPException(403, "You can only delete your own reel")
    video_url, cover_url = reel.video_url, reel.cover_url
    db.delete(reel); db.commit()
    delete_local_upload(BASE_DIR, video_url); delete_local_upload(BASE_DIR, cover_url)
    return {"message": "Reel deleted"}
