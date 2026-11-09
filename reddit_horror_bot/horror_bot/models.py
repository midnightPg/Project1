"""Modelo de dados de uma história."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class Story:
    id: str
    subreddit: str
    title: str
    author: str
    body: str
    score: int
    num_comments: int
    url: str
    created_utc: float
    flair: str | None = None
    nsfw: bool = False

    @property
    def word_count(self) -> int:
        return len(self.body.split())

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self.created_utc, tz=timezone.utc)

    @classmethod
    def from_reddit(cls, data: dict) -> "Story":
        """Constrói uma Story a partir do campo `data` de um post (kind t3)."""
        return cls(
            id=data["id"],
            subreddit=data.get("subreddit", ""),
            title=data.get("title", "").strip(),
            author=data.get("author") or "[deleted]",
            body=(data.get("selftext") or "").strip(),
            score=int(data.get("score", 0)),
            num_comments=int(data.get("num_comments", 0)),
            url="https://www.reddit.com" + data.get("permalink", ""),
            created_utc=float(data.get("created_utc", 0)),
            flair=data.get("link_flair_text"),
            nsfw=bool(data.get("over_18", False)),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["word_count"] = self.word_count
        d["created_at"] = self.created_at.isoformat()
        return d
