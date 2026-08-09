from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import Base, engine
from app.routes import (
    auth,
    calls,
    messages,
    notifications,
    posts,
    reels,
    social,
    stories,
    users,
)


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOAD_DIR = BASE_DIR / "uploads"
CUSTOM_404_PAGE = FRONTEND_DIR / "404.html"


# =========================================================
# CREATE REQUIRED UPLOAD DIRECTORIES
# =========================================================

for folder in (
    "profiles",
    "posts",
    "stories",
    "messages",
    "reels",
    "covers",
):
    (UPLOAD_DIR / folder).mkdir(parents=True, exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="SocialSphere API",
    description=(
        "Instagram-style SocialSphere with photo/video posts, "
        "stories, messages, likes, comments and notifications."
    ),
    version="5.0.0",
)
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static"
)


# =========================================================
# TEMPLATES
# =========================================================

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# STATIC FILES
# =========================================================

css_dir = FRONTEND_DIR / "css"
js_dir = FRONTEND_DIR / "js"
images_dir = FRONTEND_DIR / "images"

if css_dir.is_dir():
    app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")

if js_dir.is_dir():
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

if images_dir.is_dir():
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")

if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# =========================================================
# API ROUTERS
# =========================================================

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(stories.router)
app.include_router(social.router)
app.include_router(messages.router)
app.include_router(notifications.router)
app.include_router(reels.router)
app.include_router(calls.router)


# =========================================================
# AUTH API COMPATIBILITY ALIASES
#
# If your existing auth.py already has a POST signup/login
# route such as /signup, /auth/signup, /register, etc.,
# these aliases let the frontend safely use:
#
# POST /api/signup
# POST /api/login
#
# A 307 redirect preserves the POST method and request body.
# =========================================================

def find_post_route(keywords: tuple[str, ...], excluded: set[str]) -> str | None:
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()

        if "POST" not in methods:
            continue

        if path in excluded:
            continue

        lowered = path.lower()

        if any(lowered.endswith(keyword) for keyword in keywords):
            return path

    return None


existing_paths = {
    getattr(route, "path", "")
    for route in app.routes
}

if "/api/signup" not in existing_paths:
    signup_target = find_post_route(
        keywords=("/signup", "/register"),
        excluded={"/api/signup"},
    )

    if signup_target:
        @app.post("/api/signup", include_in_schema=False)
        async def signup_api_alias():
            return RedirectResponse(
                url=signup_target,
                status_code=307,
            )


existing_paths = {
    getattr(route, "path", "")
    for route in app.routes
}

if "/api/login" not in existing_paths:
    login_target = find_post_route(
        keywords=("/login", "/signin"),
        excluded={"/api/login"},
    )

    if login_target:
        @app.post("/api/login", include_in_schema=False)
        async def login_api_alias():
            return RedirectResponse(
                url=login_target,
                status_code=307,
            )


# =========================================================
# FRONTEND PAGES
# =========================================================

PAGES = {
    "/": "index.html",

    "/login": "login.html",
    "/login-page": "login.html",

    "/signup": "signup.html",
    "/signup-page": "signup.html",

    "/feed": "feed.html",
    "/feed-page": "feed.html",

    "/create-post": "create_post.html",
    "/create-post-page": "create_post.html",

    "/profile": "profile.html",
    "/profile-page": "profile.html",

    "/edit-profile": "edit_profile.html",
    "/edit-profile-page": "edit_profile.html",

    "/search": "search.html",
    "/search-page": "search.html",

    "/bookmarks": "bookmark.html",
    "/bookmark-page": "bookmark.html",

    "/about": "about.html",
    "/about-page": "about.html",

    "/contact": "contact.html",
    "/contact-page": "contact.html",

    "/explore": "explore.html",
    "/friends": "friends.html",
    "/messages": "message.html",
    "/notifications": "notification.html",
    "/settings": "setting.html",
    "/reels": "reels.html",
    "/create-reel": "create_reel.html",
    "/call": "call.html",
    "/privacy": "privacy.html",
    "/terms": "terms.html",
}


def page_response(filename: str):
    target = FRONTEND_DIR / filename

    if not target.is_file():
        return JSONResponse(
            {
                "success": False,
                "detail": f"Page '{filename}' is missing.",
            },
            status_code=404,
        )

    return FileResponse(target)


def make_page_handler(filename: str):
    async def page():
        return page_response(filename)

    return page


for route_path, filename in PAGES.items():
    app.add_api_route(
        route_path,
        make_page_handler(filename),
        methods=["GET"],
        include_in_schema=False,
    )


# =========================================================
# VIDEO CALL PAGE
# =========================================================

@app.get(
    "/video-call",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def video_call(request: Request):
    video_template = TEMPLATES_DIR / "video_call.html"

    if not video_template.is_file():
        return HTMLResponse(
            content=(
                "<h1>video_call.html is missing</h1>"
                "<p>Put video_call.html inside the templates folder.</p>"
            ),
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="video_call.html",
        context={},
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "message": "SocialSphere backend is running",
        "version": "5.0.0",
    }


# =========================================================
# 404 HANDLER
#
# IMPORTANT FIX:
# Missing API endpoints MUST return JSON, not 404.html.
# This prevents frontend errors such as:
# "Unexpected token '<', '<!DOCTYPE ...' is not valid JSON"
# =========================================================

@app.exception_handler(404)
async def not_found(request: Request, exc):
    path = request.url.path
    accept = request.headers.get("accept", "")

    wants_json = (
        path.startswith("/api/")
        or path.startswith("/auth/")
        or "application/json" in accept.lower()
    )

    if wants_json:
        return JSONResponse(
            {
                "success": False,
                "detail": f"API route not found: {path}",
            },
            status_code=404,
        )

    if CUSTOM_404_PAGE.is_file():
        return FileResponse(
            CUSTOM_404_PAGE,
            status_code=404,
        )

    return JSONResponse(
        {
            "success": False,
            "detail": "Not found",
        },
        status_code=404,
    )
