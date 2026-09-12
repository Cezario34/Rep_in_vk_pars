from __future__ import annotations

from .logging_setup import setup_logging
from .post_text import BookPost, build_post_text
from pathlib import Path
from .poster import run_mailing
logger = setup_logging("mailing")


def prepare_post(
    author_name: str,
    book_title: str,
    age_rating: str,
    annotation: str,
    book_links: str | list[str],
) -> str:
    text = build_post_text(
        author_name=author_name,
        book_title=book_title,
        age_rating=age_rating,
        annotation=annotation,
        book_links=book_links,
    )
    post = BookPost(
        author_name=author_name,
        book_title=book_title,
        age_rating=age_rating,
        annotation=annotation,
        book_links=book_links if isinstance(book_links, list) else [book_links],
    )
    logger.info(
        "Собран пост: автор=%s, книга=%s, ценз=%s, ссылок=%s",
        post.author_name,
        post.book_title,
        post.age_rating,
        len(post.book_links),
    )
    return text

def send_book(
    author_name: str,
    book_title: str,
    age_rating: str,
    annotation: str,
    book_links: str | list[str],
    token: str,
    day: int,
    attachment: str | None = None,
    groups_dir: str | Path = "group_target",
) -> Path:
    text = prepare_post(
        author_name=author_name,
        book_title=book_title,
        age_rating=age_rating,
        annotation=annotation,
        book_links=book_links,
    )
    return run_mailing(
        post_text=text,
        token=token,
        day=day,
        attachment=attachment,
        groups_dir=groups_dir,
    )