"""Configuração por defeito do bot."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Subreddits conhecidos por histórias de horror / creepypasta / relatos reais.
DEFAULT_SUBREDDITS = [
    "nosleep",
    "shortscarystories",
    "LetsNotMeet",
    "Glitch_in_the_Matrix",
    "Thetruthishere",
    "TrueScaryStories",
    "creepyencounters",
    "scarystories",
]

# Flairs que normalmente não são histórias (anúncios, meta, etc.).
DEFAULT_EXCLUDED_FLAIRS = {"meta", "announcement", "mod post", "discussion"}

VALID_SORTS = ("hot", "new", "top", "rising")
VALID_TIME_FILTERS = ("hour", "day", "week", "month", "year", "all")


@dataclass
class Config:
    subreddits: list[str] = field(default_factory=lambda: list(DEFAULT_SUBREDDITS))
    sort: str = "top"
    time_filter: str = "week"  # só usado com sort=top
    limit_per_subreddit: int = 50
    min_score: int = 50
    min_words: int = 300
    include_nsfw: bool = True
    excluded_flairs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_FLAIRS))
    keywords: list[str] = field(default_factory=list)  # se vazio, aceita tudo
    db_path: str = "horror_stories.db"
    output_dir: str = "stories"
    # Reddit pede um User-Agent descritivo e único.
    user_agent: str = os.environ.get(
        "REDDIT_USER_AGENT", "python:horror-story-bot:v1.0 (personal use)"
    )
    # Credenciais OAuth opcionais (recomendado: limites mais altos e mais estável).
    client_id: str | None = os.environ.get("REDDIT_CLIENT_ID")
    client_secret: str | None = os.environ.get("REDDIT_CLIENT_SECRET")
    # Segundos mínimos entre pedidos (sem OAuth o Reddit permite ~10 pedidos/min).
    request_delay: float = 6.0

    def validate(self) -> None:
        if self.sort not in VALID_SORTS:
            raise ValueError(f"sort inválido: {self.sort!r} (usa um de {VALID_SORTS})")
        if self.time_filter not in VALID_TIME_FILTERS:
            raise ValueError(
                f"time_filter inválido: {self.time_filter!r} (usa um de {VALID_TIME_FILTERS})"
            )
        if self.limit_per_subreddit < 1:
            raise ValueError("limit_per_subreddit tem de ser >= 1")
        if not self.subreddits:
            raise ValueError("indica pelo menos um subreddit")
