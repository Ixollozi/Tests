from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field

USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,32}$"
FULL_NAME_PATTERN = r"^[A-Za-zА-Яа-яЁё\s\-]{2,100}$"


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PostFilters(PaginationParams):
    q: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def get_post_filters(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> PostFilters:
    return PostFilters(page=page, page_size=page_size, q=q, date_from=date_from, date_to=date_to)


PostFiltersDep = Annotated[PostFilters, Depends(get_post_filters)]


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    full_name: str = Field(min_length=2, max_length=100, pattern=FULL_NAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None, min_length=3, max_length=32, pattern=USERNAME_PATTERN
    )
    full_name: str | None = Field(
        default=None, min_length=2, max_length=100, pattern=FULL_NAME_PATTERN
    )


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    full_name: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class RegisterResponse(BaseModel):
    user: UserOut
    verification_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PostCreate(BaseModel):
    title: str = Field(min_length=5, max_length=255)
    content: str = Field(min_length=1, max_length=10_000)


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=10_000)


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2_000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    author_id: UUID
    content: str
    created_at: datetime


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0
    comments: list[CommentOut] = []


class PostListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    likes_count: int = 0


class PaginatedPosts(BaseModel):
    items: list[PostListItem]
    page: int
    page_size: int
    total: int


class FeedPost(BaseModel):
    id: UUID
    title: str
    content: str
    likes: list[UUID]


class FeedUser(BaseModel):
    username: str
    posts: list[FeedPost]


class PaginatedFeed(BaseModel):
    items: list[FeedUser]
    page: int
    page_size: int
    total: int


class MessageOut(BaseModel):
    detail: str
    code: str = "ok"


class TaskEnqueued(BaseModel):
    detail: str
    task_id: str
    code: str = "task_enqueued"
