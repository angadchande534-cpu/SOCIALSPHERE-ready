from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserSignup(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = None


class UserLogin(BaseModel):
    identifier: str | None = Field(default=None, min_length=3, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_identifier(self):
        value = (self.identifier or self.email or "").strip()
        if not value:
            raise ValueError("Enter your email address or username")
        self.identifier = value
        return self


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=40)
    full_name: str | None = None
    email: EmailStr | None = None
    bio: str | None = None
    phone: str | None = None
    location: str | None = None
    website: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None
    bio: str | None
    phone: str | None
    location: str | None
    website: str | None
    profile_image: str | None
    created_at: datetime


class PublicUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None
    bio: str | None
    location: str | None
    website: str | None
    profile_image: str | None
    created_at: datetime
    is_following: bool = False


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class CommentOut(BaseModel):
    id: int
    text: str
    created_at: datetime
    user_id: int
    username: str
    profile_image: str | None = None


class PostOut(BaseModel):
    id: int
    caption: str
    image: str | None
    media_type: str | None = None
    created_at: datetime
    user_id: int
    username: str
    profile_image: str | None
    likes_count: int
    comments_count: int
    liked_by_me: bool = False
    bookmarked_by_me: bool = False


class StoryOut(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str | None = None
    profile_image: str | None = None
    media_url: str
    media_type: str
    caption: str | None = None
    created_at: datetime
    expires_at: datetime
    views_count: int = 0
    viewed_by_me: bool = False
    is_mine: bool = False


class NotificationOut(BaseModel):
    id: int
    kind: str
    post_id: int | None
    is_read: bool
    created_at: datetime
    actor_id: int
    actor_username: str
    actor_full_name: str | None
    actor_profile_image: str | None


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    text: str
    media_url: str | None = None
    media_type: str | None = None
    duration_seconds: float | None = None
    is_read: bool
    created_at: datetime


class ConversationOut(BaseModel):
    user_id: int
    username: str
    full_name: str | None
    profile_image: str | None
    last_message: str
    last_message_at: datetime
    last_message_sent_by_me: bool
    unread_count: int

class ReelCommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class ReelCommentOut(BaseModel):
    id: int
    text: str
    created_at: datetime
    user_id: int
    username: str
    profile_image: str | None = None


class ReelOut(BaseModel):
    id: int
    user_id: int
    username: str
    full_name: str | None = None
    profile_image: str | None = None
    caption: str
    video_url: str
    cover_url: str | None = None
    audio_name: str | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    quality_label: str = "HD"
    created_at: datetime
    likes_count: int = 0
    comments_count: int = 0
    views_count: int = 0
    liked_by_me: bool = False
