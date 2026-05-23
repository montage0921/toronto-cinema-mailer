from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Showtime:
    time: str  # e.g. "7:00 PM"
    date: str  # e.g. "2026-05-22"
    ticket_url: str = ""


@dataclass
class Movie:
    title: str
    director: str = ""
    runtime: str = ""
    year: str = ""
    language: str = ""
    description: str = ""
    poster_url: str = ""
    showtimes: list[Showtime] = field(default_factory=list)
    cinema: str = ""
    cinema_url: str = ""
    # Ratings — populated later
    letterboxd_rating: Optional[float] = None
    letterboxd_url: str = ""
    douban_rating: Optional[float] = None
    douban_url: str = ""
    douban_title: str = ""  # Chinese title from Douban


class BaseScraper(ABC):
    name: str = ""
    url: str = ""

    @abstractmethod
    def scrape(self) -> list[Movie]:
        """Return list of currently showing/upcoming movies."""
        pass

    def _clean(self, text: str) -> str:
        return " ".join(text.split()).strip()
