"""Bot que recolhe histórias de horror do Reddit."""

from .config import Config
from .models import Story
from .scraper import HorrorScraper

__all__ = ["Config", "Story", "HorrorScraper"]
__version__ = "1.0.0"
