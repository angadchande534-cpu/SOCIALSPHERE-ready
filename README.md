# SocialSphere Ultimate

A FastAPI + HTML/CSS/JavaScript social-media project with an Instagram-style UI.

## Included

- Signup/login with persistent JWT sessions
- Profiles, edit profile, follow/unfollow, followers/following
- Photo/video posts, likes, comments, bookmarks, delete own posts
- 24-hour photo/video stories and story views
- Dedicated Reels system with vertical snap feed, autoplay/pause, likes, comments, views, share link, optional cover and HD metadata
- Reel upload up to 250 MB; original upload file is preserved (720p/1080p label is based on source resolution)
- Direct messages with text, images and video
- Browser voice-note recording and audio messages
- Read/seen state and unread message counts
- Voice/video call UI using WebRTC with WebSocket signaling and a public STUN server
- Notifications, search, explore and responsive mobile navigation
- SQLite for instant local testing, PostgreSQL/Supabase-compatible DATABASE_URL for production

## Important call limitation

The included WebRTC call feature is a solid development/demo implementation. For reliable calls across restrictive mobile/carrier networks in production, configure a TURN server. The project currently uses a public STUN server only.

## 1. Create environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 2. Create `.env`

Copy `.env.example` to `.env`.

For local SQLite testing you can leave `DATABASE_URL=` blank.

For a new Supabase project, copy the PostgreSQL pooler connection string from Supabase and set it as `DATABASE_URL`. Do not commit `.env`.

Generate a JWT secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Then put it in `SECRET_KEY=`.

## 3. Run

```powershell
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

API docs: http://127.0.0.1:8000/docs

## Main pages

- `/signup`
- `/login`
- `/feed`
- `/create-post`
- `/reels`
- `/create-reel`
- `/messages`
- `/profile`
- `/search`
- `/notifications`

## Media storage

This package stores uploaded media under `uploads/` by default. The database can be Supabase PostgreSQL, but the media files are still local unless you later connect Supabase Storage or another object-storage service. For production hosting where disks are ephemeral, object storage is recommended.

## Premium UI refresh
This build includes `frontend/css/premium.css`, a global premium dark/glass visual layer with violet/pink/blue ambient gradients, improved feed cards, stories, forms, messaging, reels, calls, profile surfaces, and mobile navigation. It is loaded after the existing styles so the backend and page logic stay unchanged.
