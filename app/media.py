from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

IMAGE_TYPES = {
    "image/jpeg": (".jpg", "image"), "image/png": (".png", "image"),
    "image/webp": (".webp", "image"), "image/gif": (".gif", "image"),
}
VIDEO_TYPES = {
    "video/mp4": (".mp4", "video"), "video/webm": (".webm", "video"),
    "video/ogg": (".ogv", "video"), "video/quicktime": (".mov", "video"),
    "video/x-m4v": (".m4v", "video"),
}
AUDIO_TYPES = {
    "audio/webm": (".webm", "audio"), "audio/ogg": (".ogg", "audio"),
    "audio/mpeg": (".mp3", "audio"), "audio/mp4": (".m4a", "audio"),
    "audio/x-m4a": (".m4a", "audio"), "audio/wav": (".wav", "audio"),
}
MEDIA_TYPES = {**IMAGE_TYPES, **VIDEO_TYPES, **AUDIO_TYPES}


def media_type_from_url(url: str | None) -> str | None:
    if not url: return None
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if suffix in {".mp4", ".webm", ".ogv", ".mov", ".m4v"}: return "video"
    if suffix in {".ogg", ".mp3", ".m4a", ".wav"}: return "audio"
    return "image"


def save_upload(upload: UploadFile, destination: Path, public_prefix: str, *, max_bytes: int = 50 * 1024 * 1024, allowed_types: set[str] | None = None) -> tuple[str, str]:
    if not upload.filename: raise HTTPException(400, "Choose a file")
    content_type = upload.content_type or ""
    info = MEDIA_TYPES.get(content_type)
    if not info or (allowed_types and info[1] not in allowed_types):
        allowed = ", ".join(sorted(allowed_types or {"image", "video", "audio"}))
        raise HTTPException(400, f"Unsupported file type. Allowed: {allowed}.")
    extension, media_type = info
    data = upload.file.read()
    if not data: raise HTTPException(400, "The selected file is empty")
    if len(data) > max_bytes:
        raise HTTPException(400, f"File must be under {max_bytes // (1024 * 1024)} MB")
    destination.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    (destination / filename).write_bytes(data)
    return f"{public_prefix.rstrip('/')}/{filename}", media_type


def delete_local_upload(base_dir: Path, url: str | None) -> None:
    if not url or not url.startswith("/uploads/"): return
    try:
        target = (base_dir / "uploads" / url.removeprefix("/uploads/")).resolve()
        upload_root = (base_dir / "uploads").resolve()
        if target.is_relative_to(upload_root) and target.is_file(): target.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
