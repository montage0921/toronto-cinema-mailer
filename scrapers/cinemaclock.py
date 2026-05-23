"""
CinemaClock scraper using Playwright + BeautifulSoup.

Structure (discovered from saved HTML):
  <div class="showtimeblock movie today cin{id} movie{id}">
    <div class="movieblock">  <- title, runtime, poster
    <div class="filall ...">  <- showtimes per cinema
      <h4 class="cinemaname"> <- cinema name
      <p class="timesalso">   <- "Standard auditorium" / hall type (SKIP)
      <p class="times">       <- Today's showtimes
        <u>Today <span class="timesdate">May 22</span></u>
        <span class="tix tod" data-time="2230">22:30</span>
      <p class="timesother">  <- Other days (may be in <s> strikethrough)
        <u>Sat <span class="timesdate">May 23</span></u>
        <span class="tix" data-time="1200">12:00</span>

Times are 24h in data-time attribute (HHMM format, e.g. "2230" = 22:30).
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup
from .base import BaseScraper, Movie, Showtime

CINEMACLOCK_BASE = "https://www.cinemaclock.com/movie-theaters/"

MONTHS = {
    m.lower(): i + 1
    for i, m in enumerate(
        [
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ]
    )
}


def _parse_data_time(data_time: str) -> str:
    """Convert '2230' -> '10:30 PM', '1400' -> '2:00 PM'"""
    s = data_time.zfill(4)
    h, m = int(s[:2]), int(s[2:])
    if h == 0:
        return f"12:{m:02d} AM"
    elif h < 12:
        return f"{h}:{m:02d} AM"
    elif h == 12:
        return f"12:{m:02d} PM"
    else:
        return f"{h-12}:{m:02d} PM"


def _parse_date_span(u_tag, current_year: int) -> str | None:
    """Extract date from <u>Today <span class="timesdate">May 22</span></u>"""
    span = u_tag.find("span", class_="timesdate")
    if not span:
        return None
    date_text = span.get_text().strip()  # e.g. "May 22"
    m = re.match(r"(\w+)\s+(\d+)", date_text)
    if not m:
        return None
    mon = m.group(1).lower()[:3]
    day = int(m.group(2))
    month_num = MONTHS.get(mon)
    if not month_num:
        return None
    try:
        return datetime(current_year, month_num, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


class CinemaClockScraper(BaseScraper):
    def __init__(self, slug: str, name: str, ticket_url: str):
        self.slug = slug
        self.name = name
        self.url = ticket_url
        self._source_url = CINEMACLOCK_BASE + slug

    def scrape(self) -> list[Movie]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                locale="en-CA",
                timezone_id="America/Toronto",
            )
            page = context.new_page()
            try:
                page.goto(self._source_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)
            except PWTimeout:
                print(f"[CinemaClock] Timeout for {self.name}")
                browser.close()
                return []
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        return self._parse(soup)

    def _parse(self, soup: BeautifulSoup) -> list[Movie]:
        movies = []
        current_year = datetime.now().year

        # Each film is in <div class="showtimeblock movie ...">
        for stblock in soup.find_all(
            "div", class_=re.compile(r"showtimeblock\s+movie")
        ):
            # Title from movieblock > moviedesc > h3
            h3 = stblock.find("h3", class_="movietitle")
            if not h3:
                continue
            title_link = h3.find("a")
            title = self._clean(title_link.get_text() if title_link else h3.get_text())
            title = re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()
            if not title:
                continue

            # Runtime + year from moviegenre p
            runtime, year, poster_url = "", "", ""
            genre_p = stblock.find("p", class_="moviegenre")
            if genre_p:
                gt = genre_p.get_text(" ")
                m = re.search(r"\b(19|20)\d{2}\b", gt)
                if m:
                    year = m.group(0)
                m = re.search(r"(\d+h\d*m?)", gt)
                if m:
                    runtime = m.group(1)

            # Poster
            poster_div = stblock.find("div", class_="smallposter")
            if poster_div:
                src = poster_div.get("data-src", "") or poster_div.get("style", "")
                url_m = re.search(r'url\("?(/[^")\s]+)"?\)', src)
                if url_m:
                    poster_url = "https://www.cinemaclock.com" + url_m.group(1)

            # Showtimes from filall div
            filall = stblock.find("div", class_=re.compile(r"filall"))
            if not filall:
                continue

            showtimes = []
            seen = set()

            # Process <p class="times"> (today) and <p class="timesother"> (other days)
            for p in filall.find_all("p", class_=re.compile(r"^times")):
                if "timesalso" in (p.get("class") or []):
                    continue  # skip "Standard auditorium" labels

                # Find date from <u> tag
                u = p.find("u")
                if not u:
                    continue
                date_str = _parse_date_span(u, current_year)
                if not date_str:
                    continue

                # Find all <span class="tix"> with data-time
                for tix in p.find_all("span", class_=re.compile(r"\b(?:tix|notix)\b")):
                    data_time = tix.get("data-time", "")
                    if not data_time or not data_time.isdigit():
                        continue
                    time_12h = _parse_data_time(data_time)
                    key = (date_str, time_12h)
                    if key not in seen:
                        seen.add(key)
                        showtimes.append(
                            Showtime(
                                date=date_str,
                                time=time_12h,
                                ticket_url=self.url,
                            )
                        )

            if not showtimes:
                continue

            movies.append(
                Movie(
                    title=title,
                    runtime=runtime,
                    year=year,
                    poster_url=poster_url,
                    showtimes=showtimes,
                    cinema=self.name,
                    cinema_url=self.url,
                )
            )

        return movies


# ── Instances ─────────────────────────────────────────────────────────────────

FOX = CinemaClockScraper(
    "fox-theatre", "Fox Theatre", "https://www.foxtheatre.ca/whats-on/now-showing/"
)
TIFF_LIGHTBOX = CinemaClockScraper(
    "tiff-bell-lightbox", "TIFF Lightbox", "https://www.tiff.net/calendar"
)
YONGE_DUNDAS = CinemaClockScraper(
    "cineplex-yonge-dundas-vip",
    "Cineplex Yonge Dundas & VIP",
    "https://www.cineplex.com/Theatre/cineplex-cinemas-yonge-dundas-and-vip",
)
SCOTIABANK = CinemaClockScraper(
    "scotiabank-theatre-toronto",
    "Scotiabank Theatre",
    "https://www.cineplex.com/Theatre/scotiabank-theatre-toronto",
)
INNIS = CinemaClockScraper(
    "innis-town-hall", "Innis Town Hall", "https://innis.utoronto.ca/film/"
)
HOT_DOCS = CinemaClockScraper(
    "hot-docs-ted-rogers-cinema",
    "Hot Docs Ted Rogers Cinema",
    "https://www.hotdocs.ca/",
)
YONGE_EGLINTON = CinemaClockScraper(
    "cineplex-yonge-eglinton-vip",
    "Cineplex Yonge-Eglinton & VIP",
    "https://www.cineplex.com/Theatre/cineplex-cinemas-yongeeglinton-and-vip",
)
EMPRESS_WALK = CinemaClockScraper(
    "cineplex-empress-walk",
    "Cineplex Empress Walk",
    "https://www.cineplex.com/Theatre/cineplex-cinemas-empress-walk",
)

ALL_CINEMACLOCK_CINEMAS = [
    FOX,
    TIFF_LIGHTBOX,
    YONGE_DUNDAS,
    SCOTIABANK,
    INNIS,
    HOT_DOCS,
    YONGE_EGLINTON,
    EMPRESS_WALK,
]
SLUG_MAP = {c.slug: c for c in ALL_CINEMACLOCK_CINEMAS}
SLUG_MAP.update(
    {
        "tiff": TIFF_LIGHTBOX,
        "fox": FOX,
        "hot": HOT_DOCS,
        "scotiabank": SCOTIABANK,
        "innis": INNIS,
        "empress": EMPRESS_WALK,
        "yonge-dundas": YONGE_DUNDAS,
        "yonge-eglinton": YONGE_EGLINTON,
    }
)

if __name__ == "__main__":
    import sys

    key = sys.argv[1] if len(sys.argv) > 1 else "tiff"
    scraper = SLUG_MAP.get(key, TIFF_LIGHTBOX)
    print(f"Scraping: {scraper.name}")
    movies = scraper.scrape()
    print(f"Found {len(movies)} movies")
    for mv in movies[:5]:
        print(f"\n  {mv.title} ({mv.year}) — {mv.runtime}")
        for s in mv.showtimes[:5]:
            print(f"    {s.date}  |  {s.time}")
