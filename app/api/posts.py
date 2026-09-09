from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_verified
from app.db.session import get_db
from app.models import User
from app.schemas import (
    CommentCreate,
    CommentOut,
    MessageOut,
    PaginatedPosts,
    PostCreate,
    PostFiltersDep,
    PostListItem,
    PostOut,
    PostUpdate,
)
from app.services import posts as posts_service

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=PaginatedPosts)
def list_posts(
    db: Annotated[Session, Depends(get_db)],
    filters: PostFiltersDep,
) -> PaginatedPosts:
    return posts_service.list_posts(db, filters)


@router.post("", response_model=PostListItem, status_code=201)
def create_post(
    data: PostCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_verified)],
) -> PostListItem:
    post = posts_service.create_post(db, current_user, data)
    return PostListItem(
        id=post.id,
        author_id=post.author_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        likes_count=0,
    )


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: UUID, db: Annotated[Session, Depends(get_db)]) -> PostOut:
    return posts_service.get_post(db, post_id)


@router.patch("/{post_id}", response_model=PostListItem)
def update_post(
    post_id: UUID,
    data: PostUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_verified)],
) -> PostListItem:
    post = posts_service.update_post(db, post_id, current_user, data)
    return PostListItem(
        id=post.id,
        author_id=post.author_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        likes_count=0,
    )


@router.delete("/{post_id}", response_model=MessageOut)
def delete_post(
    post_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_verified)],
) -> MessageOut:
    posts_service.delete_post(db, post_id, current_user)
    return MessageOut(detail="Post deleted", code="post_deleted")


@router.get("/{post_id}/comments", response_model=list[CommentOut])
def list_comments(post_id: UUID, db: Annotated[Session, Depends(get_db)]) -> list[CommentOut]:
    return posts_service.list_comments(db, post_id)


@router.post("/{post_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    post_id: UUID,
    data: CommentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_verified)],
) -> CommentOut:
    comment = posts_service.add_comment(db, post_id, current_user, data)
    return CommentOut.model_validate(comment)


@router.delete("/{post_id}/comments/{comment_id}", response_model=MessageOut)
def delete_comment(
    post_id: UUID,
    comment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_verified)],
) -> MessageOut:
    posts_service.delete_comment(db, post_id, comment_id, current_user)
    return MessageOut(detail="Comment deleted", code="comment_deleted")


@router.post("/{post_id}/like", response_model=MessageOut, status_code=201)
def like_post(
    post_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageOut:
    posts_service.like_post(db, post_id, current_user)
    return MessageOut(detail="Liked", code="liked")


@router.delete("/{post_id}/like", response_model=MessageOut)
def unlike_post(
    post_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageOut:
    posts_service.unlike_post(db, post_id, current_user)
    return MessageOut(detail="Unliked", code="unliked")
