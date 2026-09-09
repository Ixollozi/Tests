from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import PaginatedFeed, PostFiltersDep
from app.services import posts as posts_service

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=PaginatedFeed)
def feed(
    db: Annotated[Session, Depends(get_db)],
    filters: PostFiltersDep,
) -> PaginatedFeed:
    return posts_service.get_feed(db, filters)


@router.get("/all", response_model=PaginatedFeed, include_in_schema=False)
def all_feed(
    db: Annotated[Session, Depends(get_db)],
    filters: PostFiltersDep,
) -> PaginatedFeed:
    return posts_service.get_feed(db, filters)
