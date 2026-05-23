import re
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper, Movie, Showtime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

DATE_PAT = re.compile(
    r"^(Today|Mon|Tue|Wed|Thu|Fri|Sat|Sun)[,\s].{0,4}(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+",
    re.IGNORECASE,
)
TIME_PAT = re.compile(r"^\d{1,2}:\d{2}\s*(am|pm)$", re.IGNORECASE)


class ParadiseScraper(BaseScraper):
    name = "Paradise on Bloor"
    url = "https://paradiseonbloor.com/coming-soon/"

    def scrape(self) -> list[Movie]:
        resp = requests.get(self.url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        movies = []

        for h2 in soup.find_all("h2"):
            title_link = h2.find("a")
            if not title_link:
                continue

            title = self._clean(title_link.text)
            container = h2.find_parent()
            if not container:
                continue

            director, runtime, year, language, description, poster_url = "", "", "", "", "", ""

            img = container.find("img")
            if img:
                poster_url = img.get("src", "")

            for p in container.find_all("p"):
                text = self._clean(p.text)
                if text.startswith("Director:"):
                    director = text.replace("Director:", "").strip().split("Run Time:")[0].strip()
                if "Run Time:" in text:
                    runtime = text.split("Run Time:")[1].strip().split("Format:")[0].strip()
                if "Release Year:" in text:
                    year = text.split("Release Year:")[1].strip().split()[0]
                if "Language:" in text:
                    language = text.split("Language:")[1].strip().split()[0]

            for p in container.find_all("p"):
                text = self._clean(p.text)
                if len(text) > 60 and not any(
                    text.startswith(k) for k in ["Director:", "Run Time:", "Starring:", "Release", "Format", "Language"]
                ):
                    description = text
                    break

            # Showtimes — walk <li> and <a> elements sequentially.
            # Date <li>s have no child <a>; time <a>s have href to /purchase/.
            showtimes = []
            current_date = ""
            seen = set()

            for el in container.find_all(["li", "a"]):
                if el.name == "li":
                    # Date label: a <li> whose direct text matches a date pattern
                    # (excludes <li>s that wrap <a> time links)
                    child_links = el.find_all("a")
                    if child_links:
                        continue  # this li wraps time links, not a date
                    raw = self._clean(el.get_text(" "))
                    if DATE_PAT.match(raw):
                        # Keep only the date portion (stop at double-space or long boilerplate)
                        current_date = raw.split("  ")[0].strip()

                elif el.name == "a":
                    time_text = self._clean(el.get_text())
                    ticket_url = el.get("href", "")
                    if TIME_PAT.match(time_text) and current_date:
                        key = (current_date, time_text)
                        if key not in seen:
                            seen.add(key)
                            showtimes.append(Showtime(
                                time=time_text,
                                date=current_date,
                                ticket_url=ticket_url,
                            ))

            if title and showtimes:
                movies.append(Movie(
                    title=title,
                    director=director,
                    runtime=runtime,
                    year=year,
                    language=language,
                    description=description,
                    poster_url=poster_url,
                    showtimes=showtimes,
                    cinema=self.name,
                    cinema_url=self.url,
                ))

        return movies


if __name__ == "__main__":
    scraper = ParadiseScraper()
    movies = scraper.scrape()
    print(f"Found {len(movies)} movies at {scraper.name}")
    for m in movies[:5]:
        print(f"\n  {m.title} ({m.year}) — {m.director}")
        print(f"  Showtimes: {len(m.showtimes)}")
        for s in m.showtimes[:3]:
            print(f"    {s.date}  |  {s.time}  |  {s.ticket_url[:55]}")
