from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Bookmark, Comment, Follow, Like, Notification, Post, User, now_utc
from app.schemas import CommentCreate, CommentOut, PublicUserOut

router = APIRouter(prefix="/api", tags=["Social"])


def add_notification(
    db: Session,
    *,
    user_id: int,
    actor_id: int,
    kind: str,
    post_id: int | None = None,
) -> None:
    if user_id == actor_id:
        return

    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.actor_id == actor_id,
            Notification.kind == kind,
            Notification.post_id == post_id,
        )
        .first()
    )
    if existing:
        existing.is_read = False
        existing.created_at = now_utc()
        return

    db.add(
        Notification(
            user_id=user_id,
            actor_id=actor_id,
            kind=kind,
            post_id=post_id,
        )
    )


def public_user(user: User, db: Session, current_id: int) -> PublicUserOut:
    return PublicUserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        bio=user.bio,
        location=user.location,
        website=user.website,
        profile_image=user.profile_image,
        created_at=user.created_at,
        is_following=(
            db.query(Follow)
            .filter(
                Follow.follower_id == current_id,
                Follow.following_id == user.id,
            )
            .first()
            is not None
        ),
    )


@router.post("/posts/{post_id}/like")
def toggle_like(
    post_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    like = (
        db.query(Like)
        .filter(Like.post_id == post_id, Like.user_id == current.id)
        .first()
    )
    if like:
        db.delete(like)
        db.query(Notification).filter(
            Notification.user_id == post.user_id,
            Notification.actor_id == current.id,
            Notification.kind == "like",
            Notification.post_id == post_id,
        ).delete(synchronize_session=False)
        liked = False
    else:
        db.add(Like(post_id=post_id, user_id=current.id))
        add_notification(
            db,
            user_id=post.user_id,
            actor_id=current.id,
            kind="like",
            post_id=post_id,
        )
        liked = True

    db.commit()
    return {
        "liked": liked,
        "likes_count": db.query(Like).filter(Like.post_id == post_id).count(),
    }


@router.get("/posts/{post_id}/likes", response_model=list[PublicUserOut])
def post_likes(
    post_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not db.get(Post, post_id):
        raise HTTPException(404, "Post not found")

    users = (
        db.query(User)
        .join(Like, Like.user_id == User.id)
        .filter(Like.post_id == post_id)
        .order_by(Like.created_at.desc())
        .all()
    )
    return [public_user(user, db, current.id) for user in users]


@router.post("/posts/{post_id}/bookmark")
def toggle_bookmark(
    post_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not db.get(Post, post_id):
        raise HTTPException(404, "Post not found")

    row = (
        db.query(Bookmark)
        .filter(Bookmark.post_id == post_id, Bookmark.user_id == current.id)
        .first()
    )
    if row:
        db.delete(row)
        saved = False
    else:
        db.add(Bookmark(post_id=post_id, user_id=current.id))
        saved = True

    db.commit()
    return {"bookmarked": saved}


@router.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    post_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    text = data.text.strip()
    if not text:
        raise HTTPException(400, "Comment cannot be empty")

    comment = Comment(
        post_id=post_id,
        user_id=current.id,
        text=text,
    )
    db.add(comment)
    add_notification(
        db,
        user_id=post.user_id,
        actor_id=current.id,
        kind="comment",
        post_id=post_id,
    )
    db.commit()
    db.refresh(comment)

    return CommentOut(
        id=comment.id,
        text=comment.text,
        created_at=comment.created_at,
        user_id=current.id,
        username=current.username,
        profile_image=current.profile_image,
    )


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
def comments(
    post_id: int,
    db: Session = Depends(get_db),
):
    if not db.get(Post, post_id):
        raise HTTPException(404, "Post not found")

    rows = (
        db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return [
        CommentOut(
            id=comment.id,
            text=comment.text,
            created_at=comment.created_at,
            user_id=comment.user_id,
            username=comment.author.username,
            profile_image=comment.author.profile_image,
        )
        for comment in rows
    ]


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(404, "Comment not found")
    if comment.user_id != current.id:
        raise HTTPException(403, "Not allowed")

    post = db.get(Post, comment.post_id)
    if post:
        db.query(Notification).filter(
            Notification.user_id == post.user_id,
            Notification.actor_id == current.id,
            Notification.kind == "comment",
            Notification.post_id == comment.post_id,
        ).delete(synchronize_session=False)

    db.delete(comment)
    db.commit()
    return {"message": "Comment deleted"}


@router.post("/users/{user_id}/follow")
def toggle_follow(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if user_id == current.id:
        raise HTTPException(400, "You cannot follow yourself")
    if not db.get(User, user_id):
        raise HTTPException(404, "User not found")

    row = (
        db.query(Follow)
        .filter(
            Follow.follower_id == current.id,
            Follow.following_id == user_id,
        )
        .first()
    )
    if row:
        db.delete(row)
        db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.actor_id == current.id,
            Notification.kind == "follow",
            Notification.post_id.is_(None),
        ).delete(synchronize_session=False)
        following = False
    else:
        db.add(Follow(follower_id=current.id, following_id=user_id))
        add_notification(
            db,
            user_id=user_id,
            actor_id=current.id,
            kind="follow",
        )
        following = True

    db.commit()
    return {
        "following": following,
        "followers_count": db.query(Follow)
        .filter(Follow.following_id == user_id)
        .count(),
    }
