from __future__ import annotations

from dataclasses import dataclass, field


def _as_links(value: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(value, str):
        parts = [item.strip() for item in value.replace(";", "\n").splitlines()]
        return [item for item in parts if item]
    return [str(item).strip() for item in value if str(item).strip()]


@dataclass(slots=True)
class BookPost:
    author_name: str
    book_title: str
    age_rating: str
    annotation: str
    book_links: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.author_name = self.author_name.strip()
        self.book_title = self.book_title.strip()
        self.age_rating = self.age_rating.strip()
        self.annotation = self.annotation.strip()
        self.book_links = _as_links(self.book_links)
        missing = [
            title
            for title, value in (
                ("имя автора", self.author_name),
                ("название книги", self.book_title),
                ("ценз", self.age_rating),
                ("аннотация", self.annotation),
            )
            if not value
        ]
        if not self.book_links:
            missing.append("ссылка на книгу")
        if missing:
            raise ValueError("Не хватает полей: " + ", ".join(missing))

    def render(self) -> str:
        links = "\n".join(self.book_links)
        return (
            f"{self.author_name}\n\n"
            f"{self.book_title}\n"
            f"{self.age_rating}\n\n"
            f"{self.annotation}\n\n"
            f"{links}"
        )


def build_post_text(
    author_name: str,
    book_title: str,
    age_rating: str,
    annotation: str,
    book_links: str | list[str],
) -> str:
    return BookPost(
        author_name=author_name,
        book_title=book_title,
        age_rating=age_rating,
        annotation=annotation,
        book_links=_as_links(book_links),
    ).render()