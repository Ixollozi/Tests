"""Static compliance check against TZ must-have surface (no DB required)."""

from app.main import app
from app.models import Comment, EmailVerificationToken, Like, Post, User
from app.workers.celery_app import celery_app

required = {
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("GET", "/auth/me"),
    ("GET", "/auth/verify-email"),
    ("PATCH", "/users/me"),
    ("GET", "/posts"),
    ("POST", "/posts"),
    ("GET", "/posts/{post_id}"),
    ("PATCH", "/posts/{post_id}"),
    ("DELETE", "/posts/{post_id}"),
    ("GET", "/posts/{post_id}/comments"),
    ("POST", "/posts/{post_id}/comments"),
    ("DELETE", "/posts/{post_id}/comments/{comment_id}"),
    ("POST", "/posts/{post_id}/like"),
    ("DELETE", "/posts/{post_id}/like"),
    ("GET", "/feed"),
    ("POST", "/admin/cleanup-unverified"),
}

found: set[tuple[str, str]] = set()
for route in app.routes:
    methods = getattr(route, "methods", None) or set()
    path = getattr(route, "path", None)
    if not path:
        continue
    for method in methods:
        if method in {"HEAD", "OPTIONS"}:
            continue
        found.add((method, path))

missing = sorted(required - found)
print("MISSING:", missing if missing else "none")
print("routes_count:", len(found))
print("has_/all:", ("GET", "/all") in found)

checks = [
    (User, {"id", "email", "username", "full_name", "password_hash", "is_verified", "created_at", "updated_at"}),
    (Post, {"id", "author_id", "title", "content", "created_at", "updated_at"}),
    (Comment, {"id", "post_id", "author_id", "content", "created_at"}),
    (Like, {"id", "user_id", "post_id", "created_at"}),
    (EmailVerificationToken, {"id", "user_id", "token", "expires_at", "created_at"}),
]
for model, cols in checks:
    have = {c.name for c in model.__table__.columns}
    miss = cols - have
    print(f"model {model.__tablename__}:", "OK" if not miss else f"missing {miss}")

print("like_unique:", any(c.name == "uq_likes_user_post" for c in Like.__table__.constraints))
print("indexes posts:", sorted(i.name for i in Post.__table__.indexes))
print("indexes likes:", sorted(i.name for i in Like.__table__.indexes))
print("beat_tasks:", list(celery_app.conf.beat_schedule.keys()))

assert not missing, missing
print("COMPLIANCE_SURFACE_OK")
