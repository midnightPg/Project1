"""Regras para decidir se um post é uma história válida."""

from __future__ import annotations

from .config import Config
from .models import Story

REMOVED_MARKERS = {"[removed]", "[deleted]", ""}


def rejection_reason(post: dict, story: Story, config: Config) -> str | None:
    """Devolve o motivo de rejeição, ou None se o post for aceite."""
    if post.get("stickied"):
        return "fixado"
    if not post.get("is_self", True):
        return "não é texto"
    if story.body in REMOVED_MARKERS or post.get("removed_by_category"):
        return "removido"
    if story.nsfw and not config.include_nsfw:
        return "nsfw"
    if story.flair and story.flair.strip().lower() in config.excluded_flairs:
        return f"flair '{story.flair}'"
    if story.score < config.min_score:
        return f"score {story.score} < {config.min_score}"
    if story.word_count < config.min_words:
        return f"{story.word_count} palavras < {config.min_words}"
    if config.keywords:
        haystack = f"{story.title}\n{story.body}".lower()
        if not any(k.lower() in haystack for k in config.keywords):
            return "sem palavras-chave"
    return None
