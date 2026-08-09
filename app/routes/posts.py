from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.media import delete_local_upload, media_type_from_url, save_upload
from app.models import Bookmark, Comment, Follow, Like, Post, User
from app.schemas import PostOut

router = APIRouter(prefix="/api/posts", tags=["Posts"])
BASE_DIR = Path(__file__).resolve().parents[2]
POST_DIR = BASE_DIR / "uploads" / "posts"


def serialize(post: Post, db: Session, current_id: int) -> PostOut:
    return PostOut(
        id=post.id,
        caption=post.caption,
        image=post.image,
        media_type=media_type_from_url(post.image),
        created_at=post.created_at,
        user_id=post.user_id,
        username=post.author.username,
        profile_image=post.author.profile_image,
        likes_count=db.query(Like).filter(Like.post_id == post.id).count(),
        comments_count=db.query(Comment).filter(Comment.post_id == post.id).count(),
        liked_by_me=db.query(Like).filter(
            Like.post_id == post.id, Like.user_id == current_id
        ).first() is not None,
        bookmarked_by_me=db.query(Bookmark).filter(
            Bookmark.post_id == post.id, Bookmark.user_id == current_id
        ).first() is not None,
    )


@router.post("", response_model=PostOut, status_code=201)
def create_post(
    caption: str = Form(""),
    media: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    selected = media if media and media.filename else image
    media_url = None
    if selected and selected.filename:
        media_url, _media_type = save_upload(
            selected,
            POST_DIR,
            "/uploads/posts",
            max_bytes=60 * 1024 * 1024,
        )

    clean_caption = caption.strip()
    if not clean_caption and not media_url:
        raise HTTPException(400, "Add a caption, photo or video")

    post = Post(user_id=current.id, caption=clean_caption, image=media_url)
    db.add(post)
    db.commit()
    db.refresh(post)
    return serialize(post, db, current.id)


@router.get("", response_model=list[PostOut])
def all_posts(
    skip: int = 0,
    limit: int = 30,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    posts = (
        db.query(Post)
        .order_by(Post.created_at.desc())
        .offset(max(skip, 0))
        .limit(min(max(limit, 1), 100))
        .all()
    )
    return [serialize(post, db, current.id) for post in posts]


@router.get("/feed", response_model=list[PostOut])
def feed(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    ids = [
        row[0]
        for row in db.query(Follow.following_id)
        .filter(Follow.follower_id == current.id)
        .all()
    ] + [current.id]
    posts = (
        db.query(Post)
        .filter(Post.user_id.in_(ids))
        .order_by(Post.created_at.desc())
        .limit(60)
        .all()
    )
    return [serialize(post, db, current.id) for post in posts]


@router.get("/bookmarks", response_model=list[PostOut])
def bookmarked_posts(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    posts = (
        db.query(Post)
        .join(Bookmark, Bookmark.post_id == Post.id)
        .filter(Bookmark.user_id == current.id)
        .order_by(Post.created_at.desc())
        .all()
    )
    return [serialize(post, db, current.id) for post in posts]


@router.get("/user/{user_id}", response_model=list[PostOut])
def user_posts(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    posts = (
        db.query(Post)
        .filter(Post.user_id == user_id)
        .order_by(Post.created_at.desc())
        .all()
    )
    return [serialize(post, db, current.id) for post in posts]


@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post.user_id != current.id:
        raise HTTPException(403, "You can only delete your own post")

    media_url = post.image
    db.delete(post)
    db.commit()
    delete_local_upload(BASE_DIR, media_url)
    return {"message": "Post deleted"}
