from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Follow, Post, User
from app.schemas import PublicUserOut, UserOut

router = APIRouter(prefix="/api/users", tags=["Users"])
BASE_DIR = Path(__file__).resolve().parents[2]
PROFILE_DIR = BASE_DIR / "uploads" / "profiles"
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def public_user(user: User, db: Session, current_id: int) -> PublicUserOut:
    is_following = (
        db.query(Follow)
        .filter(
            Follow.follower_id == current_id,
            Follow.following_id == user.id,
        )
        .first()
        is not None
    )
    return PublicUserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        bio=user.bio,
        location=user.location,
        website=user.website,
        profile_image=user.profile_image,
        created_at=user.created_at,
        is_following=is_following,
    )


@router.get("/search", response_model=list[PublicUserOut])
def search(
    q: str = "",
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    query = q.strip()
    if not query:
        return []

    users = (
        db.query(User)
        .filter(
            User.id != current.id,
            or_(
                User.username.ilike(f"%{query}%"),
                User.full_name.ilike(f"%{query}%"),
            ),
        )
        .order_by(User.username.asc())
        .limit(30)
        .all()
    )
    return [public_user(user, db, current.id) for user in users]


@router.get("/{user_id}/followers", response_model=list[PublicUserOut])
def followers(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not db.get(User, user_id):
        raise HTTPException(404, "User not found")

    users = (
        db.query(User)
        .join(Follow, Follow.follower_id == User.id)
        .filter(Follow.following_id == user_id)
        .order_by(Follow.created_at.desc())
        .all()
    )
    return [public_user(user, db, current.id) for user in users]


@router.get("/{user_id}/following", response_model=list[PublicUserOut])
def following(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if not db.get(User, user_id):
        raise HTTPException(404, "User not found")

    users = (
        db.query(User)
        .join(Follow, Follow.following_id == User.id)
        .filter(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .all()
    )
    return [public_user(user, db, current.id) for user in users]


@router.get("/{user_id}")
def profile(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    return {
        "user": public_user(user, db, current.id),
        "posts_count": db.query(Post).filter(Post.user_id == user_id).count(),
        "followers_count": db.query(Follow)
        .filter(Follow.following_id == user_id)
        .count(),
        "following_count": db.query(Follow)
        .filter(Follow.follower_id == user_id)
        .count(),
        "is_following": db.query(Follow)
        .filter(
            Follow.follower_id == current.id,
            Follow.following_id == user_id,
        )
        .first()
        is not None,
        "is_me": current.id == user_id,
    }


@router.put("/me", response_model=UserOut)
def update_me(
    username: str = Form(...),
    full_name: str = Form(""),
    email: str = Form(...),
    bio: str = Form(""),
    phone: str = Form(""),
    location: str = Form(""),
    website: str = Form(""),
    profile_image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    conflict = (
        db.query(User)
        .filter(
            User.id != current.id,
            or_(
                User.username == username.strip(),
                User.email == email.lower().strip(),
            ),
        )
        .first()
    )
    if conflict:
        raise HTTPException(400, "Username or email is already in use")

    current.username = username.strip()
    current.full_name = full_name.strip() or None
    current.email = email.lower().strip()
    current.bio = bio.strip() or None
    current.phone = phone.strip() or None
    current.location = location.strip() or None
    current.website = website.strip() or None

    if profile_image and profile_image.filename:
        if profile_image.content_type not in ALLOWED:
            raise HTTPException(400, "Only JPG, PNG and WEBP images are allowed")
        data = profile_image.file.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(400, "Image must be under 5 MB")
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{uuid4().hex}{ALLOWED[profile_image.content_type]}"
        (PROFILE_DIR / name).write_bytes(data)
        current.profile_image = f"/uploads/profiles/{name}"

    db.commit()
    db.refresh(current)
    return current
