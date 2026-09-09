from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.schemas import (
    RegisterResponse,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
    UserUpdate,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(data: UserRegister, db: Annotated[Session, Depends(get_db)]) -> RegisterResponse:
    user, token = auth_service.register_user(db, data)
    return RegisterResponse(
        user=UserOut.model_validate(user),
        verification_token=token if settings.debug else None,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    access_token = auth_service.login_user(db, data)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserOut)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.get("/verify-email", response_model=UserOut)
def verify_email(token: str, db: Annotated[Session, Depends(get_db)]) -> User:
    return auth_service.verify_email(db, token)


users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.patch("/me", response_model=UserOut)
def update_me(
    data: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return auth_service.update_profile(db, current_user, data)
