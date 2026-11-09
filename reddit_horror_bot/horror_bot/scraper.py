"""Orquestra a recolha: buscar → filtrar → gravar → exportar."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

from .client import RedditClient
from .config import Config
from .filters import rejection_reason
from .models import Story
from .storage import StoryDB, export_markdown

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    seen: int = 0
    new: int = 0
    updated: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        key = reason.split(" ")[0]
        self.rejected[key] = self.rejected.get(key, 0) + 1


class HorrorScraper:
    def __init__(self, config: Config, client: RedditClient | None = None,
                 db: StoryDB | None = None):
        config.validate()
        self.config = config
        self.client = client or RedditClient(config)
        self.db = db or StoryDB(config.db_path)

    def run_once(self, export: bool = True) -> tuple[RunStats, list[Story]]:
        stats = RunStats()
        new_stories: list[Story] = []
        for sub in self.config.subreddits:
            log.info("A recolher r/%s (%s)...", sub, self.config.sort)
            try:
                posts = self.client.iter_posts(
                    sub, self.config.sort, self.config.limit_per_subreddit,
                    self.config.time_filter,
                )
                for post in posts:
                    stats.seen += 1
                    story = Story.from_reddit(post)
                    reason = rejection_reason(post, story, self.config)
                    if reason:
                        stats.reject(reason)
                        log.debug("Rejeitado %s (%s): %s", story.id, story.title[:40], reason)
                        continue
                    if self.db.save(story):
                        stats.new += 1
                        new_stories.append(story)
                        if export:
                            export_markdown(story, self.config.output_dir)
                        log.info("  + [%d] %s", story.score, story.title)
                    else:
                        stats.updated += 1
            except requests.RequestException as exc:
                # Um subreddit privado/banido/inexistente não deve parar o bot.
                stats.errors[sub] = str(exc)
                log.error("Falha em r/%s: %s", sub, exc)
        return stats, new_stories
