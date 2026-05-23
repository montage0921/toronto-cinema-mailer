import re
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper, Movie, Showtime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

# Matches: "Friday May 15th @ 06:45 PM" or "Saturday May 16th @ 03:30 PM"
SHOWTIME_PAT = re.compile(
    r"(\w+\s+\w+\s+\d+\w*)\s*@\s*(\d{1,2}:\d{2}\s*[AP]M)",
    re.IGNORECASE,
)


class RevueScraper(BaseScraper):
    name = "Revue Cinema"
    url = "https://revuecinema.ca/films/"

    def scrape(self) -> list[Movie]:
        movies = []
        film_urls = self._collect_film_urls()
        print(f"[Revue] Found {len(film_urls)} film pages")

        for url in film_urls:
            movie = self._scrape_film_page(url)
            if movie:
                movies.append(movie)

        return movies

    def _collect_film_urls(self) -> list[str]:
        """Collect all individual film page URLs from the listing page."""
        urls = []
        seen = set()
        page = 1

        while True:
            list_url = self.url if page == 1 else f"{self.url}?paged={page}"
            try:
                resp = requests.get(list_url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                print(f"[Revue] Listing page {page} failed: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            found = 0
            for a in soup.select("a[href*='/films/']"):
                href = a.get("href", "").rstrip("/")
                # Must be /films/slug/ — at least 3 path segments, not the index
                parts = [p for p in href.split("/") if p]
                if len(parts) < 3 or href in seen:
                    continue
                if href == self.url.rstrip("/"):
                    continue
                seen.add(href)
                urls.append(href + "/")
                found += 1

            if found == 0:
                break
            page += 1
            if page > 10:
                break

        return urls

    def _scrape_film_page(self, url: str) -> Movie | None:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Revue] Film page failed {url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title — the <h1>
        h1 = soup.find("h1")
        if not h1:
            return None
        title = re.sub(r"\s*\(\d{4}\)\s*$", "", self._clean(h1.get_text()))

        # Metadata line: "Runtime: 111 mins | Release Year: 2026 | Rating: R | Genre(s): Comedy"
        director, runtime, year, language, description, poster_url = "", "", "", "", "", ""

        full_text = soup.get_text(" ")

        m = re.search(r"Runtime:\s*([\d]+\s*mins?)", full_text, re.I)
        if m:
            runtime = m.group(1)

        m = re.search(r"Release Year:\s*(\d{4})", full_text, re.I)
        if m:
            year = m.group(1)

        m = re.search(r"Original Language:\s*([^\n|]+)", full_text, re.I)
        if m:
            lang = self._clean(m.group(1))
            if lang.lower() != "english":
                language = lang

        # Director from Cast/Crew section: "Director: Chandler Levack | Cast: ..."
        m = re.search(r"Director:\s*([^|}\n]+?)(?:\s*\||\s*Cast:)", full_text, re.I)
        if m:
            director = self._clean(m.group(1))

        # Description — the main body paragraph (before Showtimes heading)
        content = soup.select_one("article, .entry-content, main, #brx-content")
        if content:
            paras = [self._clean(p.get_text()) for p in content.find_all("p")
                     if len(p.get_text().strip()) > 60]
            if paras:
                description = max(paras, key=len)

        # Poster
        img = soup.select_one(".wp-post-image, article img, .film-poster img, main img")
        if img:
            poster_url = img.get("src", "")

        # Buy Tickets link — find by href pattern (agileticketing) or text match
        ticket_url = url  # fallback to film page itself
        # Try agileticketing direct link first
        ticket_link = soup.find("a", href=re.compile(r"agileticketing|ticketing", re.I))
        if not ticket_link:
            # Try by text content
            for a in soup.find_all("a"):
                if re.search(r"buy.?tickets", a.get_text(), re.I):
                    ticket_link = a
                    break
        if ticket_link:
            ticket_url = ticket_link.get("href", url)

        # Showtimes: "‣ Friday May 15th @ 06:45 PM"
        showtimes = []
        for m in SHOWTIME_PAT.finditer(full_text):
            date_str = self._clean(m.group(1))
            time_str = self._clean(m.group(2))
            showtimes.append(Showtime(
                date=date_str,
                time=time_str,
                ticket_url=ticket_url,
            ))

        if not showtimes:
            return None  # Skip non-screening entries (rentals, etc.)

        return Movie(
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
        )


if __name__ == "__main__":
    scraper = RevueScraper()
    movies = scraper.scrape()
    print(f"\nFound {len(movies)} movies at {scraper.name}")
    for m in movies[:5]:
        print(f"\n  {m.title} ({m.year}) — {m.director}")
        print(f"  Runtime: {m.runtime}")
        for s in m.showtimes[:3]:
            print(f"    {s.date}  |  {s.time}  |  {s.ticket_url[:60]}")
