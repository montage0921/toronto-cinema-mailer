# Fox Theatre scraper — thin wrapper around CinemaClockScraper
from .cinemaclock import FOX as _scraper
from .base import Movie

class FoxScraper:
    name = _scraper.name
    url = _scraper.url
    def scrape(self) -> list[Movie]:
        return _scraper.scrape()

if __name__ == "__main__":
    movies = FoxScraper().scrape()
    print(f"Found {len(movies)} movies at Fox Theatre")
    for m in movies[:5]:
        print(f"\n  {m.title} — {m.runtime}")
        for s in m.showtimes[:3]:
            print(f"    {s.date}  |  {s.time}")
