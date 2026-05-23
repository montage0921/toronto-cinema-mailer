import re
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
from urllib.parse import urlparse, parse_qs
from .base import BaseScraper, Movie, Showtime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

BASE_URL = "https://imaginecinemas.com/cinema/carlton/"
DAYS_AHEAD = 7  # scrape today + next 6 days


class CarltonScraper(BaseScraper):
    name = "Imagine Cinemas Carlton"
    url = BASE_URL

    def scrape(self) -> list[Movie]:
        # movie_title -> Movie (accumulating showtimes across days)
        movies: dict[str, Movie] = {}

        today = date.today()
        for i in range(DAYS_AHEAD):
            day = today + timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            page_url = f"{BASE_URL}?schdate={day_str}"

            try:
                resp = requests.get(page_url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                print(f"[Carlton] Failed {day_str}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            self._parse_day(soup, day_str, movies)

        return list(movies.values())

    def _parse_day(self, soup: BeautifulSoup, day_str: str, movies: dict):
        for h2 in soup.find_all("h2"):
            title = self._clean(h2.get_text())
            # Strip trailing (year) like "(2004)"
            title = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()
            if not title or len(title) < 2:
                continue

            container = h2.find_parent()
            if not container:
                continue

            # If movie not seen yet, extract metadata
            if title not in movies:
                runtime, description, poster_url = "", "", ""

                img = container.find("img")
                if img:
                    poster_url = img.get("src", "")

                meta_text = container.get_text(" ")

                m = re.search(r"([\dh\s]+min)", meta_text)
                if m:
                    runtime = self._clean(m.group(1))

                syn = re.search(r"Show Synopsis\s*(.+?)\s*Hide Synopsis", meta_text, re.DOTALL)
                if syn:
                    description = self._clean(syn.group(1))

                movies[title] = Movie(
                    title=title,
                    runtime=runtime,
                    description=description,
                    poster_url=poster_url,
                    showtimes=[],
                    cinema=self.name,
                    cinema_url=self.url,
                )

            # Showtimes for this day
            seen_times = {(s.date, s.time) for s in movies[title].showtimes}

            for a in container.find_all("a", href=True):
                time_text = self._clean(a.get_text())
                if not re.match(r"\d{1,2}:\d{2}[AP]M", time_text):
                    continue

                href = a["href"]

                # Extract date from ticket URL schdate param; fallback to day_str
                extracted_date = day_str
                if "schdate=" in href:
                    qs = parse_qs(urlparse(href).query)
                    if "schdate" in qs:
                        extracted_date = qs["schdate"][0]

                ticket_url = href if href != "#" else ""
                key = (extracted_date, time_text)
                if key not in seen_times:
                    seen_times.add(key)
                    movies[title].showtimes.append(Showtime(
                        date=extracted_date,
                        time=time_text,
                        ticket_url=ticket_url,
                    ))


if __name__ == "__main__":
    scraper = CarltonScraper()
    movies = scraper.scrape()
    print(f"Found {len(movies)} movies at {scraper.name}")
    for m in movies[:5]:
        print(f"\n  {m.title} — {m.runtime}")
        for s in m.showtimes[:4]:
            print(f"    {s.date}  |  {s.time}  |  {s.ticket_url[:55]}")
