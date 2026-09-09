import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import EmailVerificationToken, User
from app.schemas import UserLogin, UserRegister, UserUpdate

logger = logging.getLogger(__name__)


def register_user(db: Session, data: UserRegister) -> tuple[User, str]:
    email = str(data.email).lower()
    existing = db.scalar(
        select(User).where((User.email == email) | (User.username == data.username))
    )
    if existing:
        if existing.email == email:
            raise AppError("Email already registered", "email_taken", status.HTTP_400_BAD_REQUEST)
        raise AppError("Username already taken", "username_taken", status.HTTP_400_BAD_REQUEST)

    user = User(
        email=email,
        username=data.username,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        is_verified=False,
    )
    db.add(user)
    db.flush()

    token = _create_verification_token(db, user)
    db.commit()
    db.refresh(user)
    logger.info("Verification token for %s: %s", user.email, token)
    return user, token


def login_user(db: Session, data: UserLogin) -> str:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise AppError(
            "Invalid email or password",
            "invalid_credentials",
            status.HTTP_401_UNAUTHORIZED,
        )
    return create_access_token(user.id)


def verify_email(db: Session, token: str) -> User:
    record = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token == token))
    if record is None:
        raise AppError(
            "Invalid verification token",
            "invalid_verification_token",
            status.HTTP_400_BAD_REQUEST,
        )

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise AppError(
            "Verification token expired",
            "verification_token_expired",
            status.HTTP_400_BAD_REQUEST,
        )

    user = db.get(User, record.user_id)
    if user is None:
        raise AppError("User not found", "user_not_found", status.HTTP_404_NOT_FOUND)

    user.is_verified = True
    db.delete(record)
    db.commit()
    db.refresh(user)
    return user


def update_profile(db: Session, user: User, data: UserUpdate) -> User:
    if data.username is not None and data.username != user.username:
        taken = db.scalar(select(User).where(User.username == data.username, User.id != user.id))
        if taken:
            raise AppError("Username already taken", "username_taken", status.HTTP_400_BAD_REQUEST)
        user.username = data.username
    if data.full_name is not None:
        user.full_name = data.full_name
    db.commit()
    db.refresh(user)
    return user


def cleanup_unverified_users(db: Session, older_than_hours: int | None = None) -> int:
    ttl = older_than_hours or settings.unverified_user_ttl_hours
    cutoff = datetime.now(UTC) - timedelta(hours=ttl)
    users = db.scalars(
        select(User).where(User.is_verified.is_(False), User.created_at < cutoff)
    ).all()
    count = len(users)
    for user in users:
        db.delete(user)
    db.commit()
    return count


def _create_verification_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    record = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.verification_token_ttl_hours),
    )
    db.add(record)
    return token
