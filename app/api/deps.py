from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("Not authenticated", "unauthorized", status.HTTP_401_UNAUTHORIZED)
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise AppError(
            "Invalid or expired token",
            "invalid_token",
            status.HTTP_401_UNAUTHORIZED,
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise AppError("User not found", "user_not_found", status.HTTP_401_UNAUTHORIZED)
    return user


def require_verified(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_verified:
        raise AppError(
            "Email verification required",
            "email_not_verified",
            status.HTTP_403_FORBIDDEN,
        )
    return user
