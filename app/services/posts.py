from uuid import UUID

from fastapi import status
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from app.core.exceptions import AppError
from app.models import Comment, Like, Post, User
from app.schemas import (
    CommentCreate,
    CommentOut,
    FeedPost,
    FeedUser,
    PaginatedFeed,
    PaginatedPosts,
    PostCreate,
    PostFilters,
    PostListItem,
    PostOut,
    PostUpdate,
)


def list_posts(db: Session, filters: PostFilters) -> PaginatedPosts:
    stmt = select(Post)
    stmt = _apply_post_filters(stmt, filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    posts = db.scalars(
        stmt.options(selectinload(Post.likes))
        .order_by(Post.created_at.desc())
        .offset(filters.offset)
        .limit(filters.page_size)
    ).all()
    items = [
        PostListItem(
            id=p.id,
            author_id=p.author_id,
            title=p.title,
            content=p.content,
            created_at=p.created_at,
            updated_at=p.updated_at,
            likes_count=len(p.likes),
        )
        for p in posts
    ]
    return PaginatedPosts(
        items=items, page=filters.page, page_size=filters.page_size, total=total
    )


def create_post(db: Session, author: User, data: PostCreate) -> Post:
    post = Post(author_id=author.id, title=data.title, content=data.content)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def get_post(db: Session, post_id: UUID) -> PostOut:
    post = db.scalar(
        select(Post)
        .where(Post.id == post_id)
        .options(selectinload(Post.comments), selectinload(Post.likes))
    )
    if post is None:
        raise AppError("Post not found", "post_not_found", status.HTTP_404_NOT_FOUND)
    return PostOut(
        id=post.id,
        author_id=post.author_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        likes_count=len(post.likes),
        comments=[CommentOut.model_validate(c) for c in post.comments],
    )


def update_post(db: Session, post_id: UUID, author: User, data: PostUpdate) -> Post:
    post = db.get(Post, post_id)
    if post is None or post.author_id != author.id:
        raise AppError("Post not found", "post_not_found", status.HTTP_404_NOT_FOUND)
    if data.title is not None:
        post.title = data.title
    if data.content is not None:
        post.content = data.content
    db.commit()
    db.refresh(post)
    return post


def delete_post(db: Session, post_id: UUID, author: User) -> None:
    post = db.get(Post, post_id)
    if post is None or post.author_id != author.id:
        raise AppError("Post not found", "post_not_found", status.HTTP_404_NOT_FOUND)
    db.delete(post)
    db.commit()


def list_comments(db: Session, post_id: UUID) -> list[CommentOut]:
    post = db.get(Post, post_id)
    if post is None:
        raise AppError("Post not found", "post_not_found", status.HTTP_404_NOT_FOUND)
    comments = db.scalars(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at.asc())
    ).all()
    return [CommentOut.model_validate(c) for c in comments]


def add_comment(db: Session, post_id: UUID, author: User, data: CommentCreate) -> Comment:
    post = db.get(Post, post_id)
    if post is None:
        raise AppError("Post not found", "post_not_found", status.HTTP_404_NOT_FOUND)
    comment = Comment(post_id=post_id, author_id=author.id, content=data.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, post_id: UUID, comment_id: UUID, author: User) -> None:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.post_id != post_id or comment.author_id != author.id:
        raise AppError("Comment not found", "comment_not_found", status.HTTP_404_NOT_FOUND)
    db.delete(comment)
    db.commit()


def like_post(db: Session, post_id: UUID, user: User) -> None:
    post = db.get(Post, post_id)
    if post is None:
        raise AppError("Post not found", "post_not_found", status.HTTP_404_NOT_FOUND)
    if post.author_id == user.id:
        raise AppError(
            "Cannot like your own post",
            "cannot_like_own_post",
            status.HTTP_400_BAD_REQUEST,
        )
    existing = db.scalar(select(Like).where(Like.post_id == post_id, Like.user_id == user.id))
    if existing:
        raise AppError("Post already liked", "already_liked", status.HTTP_400_BAD_REQUEST)
    db.add(Like(user_id=user.id, post_id=post_id))
    db.commit()


def unlike_post(db: Session, post_id: UUID, user: User) -> None:
    like = db.scalar(select(Like).where(Like.post_id == post_id, Like.user_id == user.id))
    if like is None:
        raise AppError("Like not found", "like_not_found", status.HTTP_404_NOT_FOUND)
    db.delete(like)
    db.commit()


def get_feed(db: Session, filters: PostFilters) -> PaginatedFeed:
    """Paginate users; load posts+likes via selectinload (fixed SQL count, no N+1)."""
    post_filters = _post_filter_clauses(filters)

    if post_filters:
        matching_author_ids = select(Post.author_id).where(*post_filters).distinct()
        users_stmt = select(User).where(User.id.in_(matching_author_ids))
    else:
        users_stmt = select(User)

    total = db.scalar(select(func.count()).select_from(users_stmt.subquery())) or 0

    options: list = [selectinload(User.posts).selectinload(Post.likes)]
    if filters.q or filters.date_from or filters.date_to:
        q = filters.q
        date_from = filters.date_from
        date_to = filters.date_to

        def post_loader_criterion(cls: type[Post]):
            clauses = []
            if q:
                pattern = f"%{q}%"
                clauses.append(or_(cls.title.ilike(pattern), cls.content.ilike(pattern)))
            if date_from:
                clauses.append(cls.created_at >= date_from)
            if date_to:
                clauses.append(cls.created_at <= date_to)
            return and_(*clauses) if len(clauses) > 1 else clauses[0]

        options.append(
            with_loader_criteria(Post, post_loader_criterion, include_aliases=True)
        )

    users = db.scalars(
        users_stmt.options(*options)
        .order_by(User.username.asc())
        .offset(filters.offset)
        .limit(filters.page_size)
    ).unique().all()

    items = [
        FeedUser(
            username=user.username,
            posts=[
                FeedPost(
                    id=post.id,
                    title=post.title,
                    content=post.content,
                    likes=[like.user_id for like in post.likes],
                )
                for post in sorted(user.posts, key=lambda p: p.created_at, reverse=True)
            ],
        )
        for user in users
    ]
    return PaginatedFeed(items=items, page=filters.page, page_size=filters.page_size, total=total)


def _post_filter_clauses(filters: PostFilters) -> list:
    clauses = []
    if filters.q:
        pattern = f"%{filters.q}%"
        clauses.append(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))
    if filters.date_from:
        clauses.append(Post.created_at >= filters.date_from)
    if filters.date_to:
        clauses.append(Post.created_at <= filters.date_to)
    return clauses


def _apply_post_filters(stmt: Select, filters: PostFilters) -> Select:
    for clause in _post_filter_clauses(filters):
        stmt = stmt.where(clause)
    return stmt
