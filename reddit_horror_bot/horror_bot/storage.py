"""Persistência em SQLite (evita duplicados) e exportação para ficheiros."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .models import Story

SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    id            TEXT PRIMARY KEY,
    subreddit     TEXT NOT NULL,
    title         TEXT NOT NULL,
    author        TEXT,
    body          TEXT NOT NULL,
    score         INTEGER,
    num_comments  INTEGER,
    url           TEXT,
    created_utc   REAL,
    flair         TEXT,
    nsfw          INTEGER,
    word_count    INTEGER,
    scraped_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_stories_sub ON stories(subreddit);
"""

COLUMNS = ("id", "subreddit", "title", "author", "body", "score", "num_comments",
           "url", "created_utc", "flair", "nsfw")


class StoryDB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def exists(self, story_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM stories WHERE id = ?", (story_id,)
        ).fetchone() is not None

    def save(self, story: Story) -> bool:
        """Grava a história. Devolve True se for nova; se já existir, atualiza score."""
        if self.exists(story.id):
            self.conn.execute(
                "UPDATE stories SET score = ?, num_comments = ? WHERE id = ?",
                (story.score, story.num_comments, story.id),
            )
            self.conn.commit()
            return False
        self.conn.execute(
            "INSERT INTO stories (id, subreddit, title, author, body, score, num_comments,"
            " url, created_utc, flair, nsfw, word_count)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (story.id, story.subreddit, story.title, story.author, story.body, story.score,
             story.num_comments, story.url, story.created_utc, story.flair, int(story.nsfw),
             story.word_count),
        )
        self.conn.commit()
        return True

    def all(self, subreddit: str | None = None, order_by_score: bool = True) -> list[Story]:
        sql = "SELECT * FROM stories"
        args: tuple = ()
        if subreddit:
            sql += " WHERE lower(subreddit) = lower(?)"
            args = (subreddit,)
        sql += " ORDER BY score DESC" if order_by_score else " ORDER BY created_utc DESC"
        rows = self.conn.execute(sql, args).fetchall()
        return [Story(**{c: (bool(r[c]) if c == "nsfw" else r[c]) for c in COLUMNS})
                for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]

    def close(self) -> None:
        self.conn.close()


def _slug(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_-]+", "-", text)[:max_len].strip("-") or "historia"


def export_markdown(story: Story, output_dir: str) -> Path:
    folder = Path(output_dir) / story.subreddit
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{story.id}-{_slug(story.title)}.md"
    path.write_text(
        f"# {story.title}\n\n"
        f"- **Autor:** u/{story.author}\n"
        f"- **Subreddit:** r/{story.subreddit}\n"
        f"- **Score:** {story.score} · **Comentários:** {story.num_comments}\n"
        f"- **Data:** {story.created_at:%Y-%m-%d %H:%M} UTC\n"
        f"- **Palavras:** {story.word_count}\n"
        f"- **Link:** {story.url}\n\n---\n\n{story.body}\n",
        encoding="utf-8",
    )
    return path


def export_json(stories: list[Story], path: str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([s.to_dict() for s in stories], ensure_ascii=False, indent=2),
                   encoding="utf-8")
    return out
