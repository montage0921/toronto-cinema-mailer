"""
Scheduler — runs two jobs:
  1. scrape_all_cinemas()  — daily at 8 AM Toronto time, updates DB cache
  2. send_digests()        — daily at 9 AM for daily subscribers,
                             weekly on Friday 9 AM for weekly subscribers

Run with:  python3 -m scheduler.jobs
"""
import os
import sys
import logging
from datetime import datetime, date, timedelta
import pytz

from apscheduler.schedulers.blocking import BlockingScheduler
from supabase import create_client

# Scrapers
from scrapers.paradise import ParadiseScraper
from scrapers.revue import RevueScraper
from scrapers.carlton import CarltonScraper
from scrapers.cinemaclock import (
    FOX, TIFF_LIGHTBOX, YONGE_DUNDAS, SCOTIABANK,
    INNIS, HOT_DOCS, YONGE_EGLINTON, EMPRESS_WALK,
)
from scrapers.letterboxd import enrich_movies_with_ratings
from mailer.builder import EmailContext, build_email_html
from mailer.sender import send_digest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TORONTO_TZ = pytz.timezone("America/Toronto")
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BASE_URL = os.environ.get("BASE_URL", "https://your-domain.com")

SCRAPERS = {
    "paradise":       ParadiseScraper(),
    "revue":          RevueScraper(),
    "carlton":        CarltonScraper(),
    "fox":            FOX,
    "tiff":           TIFF_LIGHTBOX,
    "yonge-dundas":   YONGE_DUNDAS,
    "scotiabank":     SCOTIABANK,
    "innis":          INNIS,
    "hot-docs":       HOT_DOCS,
    "yonge-eglinton": YONGE_EGLINTON,
    "empress-walk":   EMPRESS_WALK,
}


def get_db():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── Job 1: Scrape ─────────────────────────────────────────────────────────────

def scrape_all_cinemas():
    log.info("=== Starting scrape job ===")
    db = get_db()

    for slug, scraper in SCRAPERS.items():
        log.info(f"Scraping {scraper.name}...")
        try:
            movies = scraper.scrape()
            log.info(f"  → {len(movies)} movies found")

            # Enrich with Letterboxd ratings
            enrich_movies_with_ratings(movies, delay=1.5)

            # Upsert movies into DB
            for movie in movies:
                # Upsert movie record
                movie_row = {
                    "cinema_slug": slug,
                    "title": movie.title,
                    "director": movie.director or None,
                    "runtime": movie.runtime or None,
                    "year": movie.year or None,
                    "language": movie.language or None,
                    "description": movie.description or None,
                    "poster_url": movie.poster_url or None,
                    "letterboxd_rating": movie.letterboxd_rating,
                    "letterboxd_url": movie.letterboxd_url or None,
                    "scraped_at": datetime.now(TORONTO_TZ).isoformat(),
                }
                result = db.table("movies").upsert(
                    movie_row,
                    on_conflict="cinema_slug,title"
                ).execute()

                if not result.data:
                    continue
                movie_id = result.data[0]["id"]

                # Upsert showtimes
                for st in movie.showtimes:
                    try:
                        show_date = _parse_date(st.date)
                    except Exception:
                        continue
                    db.table("showtimes").upsert({
                        "movie_id": movie_id,
                        "show_date": show_date,
                        "show_time": st.time,
                        "ticket_url": st.ticket_url or None,
                    }, on_conflict="movie_id,show_date,show_time").execute()

        except Exception as e:
            log.error(f"  ✗ Scrape failed for {scraper.name}: {e}", exc_info=True)

    log.info("=== Scrape job done ===")


def _parse_date(date_str: str) -> str:
    """Convert 'Today, May 22' / 'Sat, May 23' / 'Sat May 23' to YYYY-MM-DD."""
    import re
    from datetime import date as dt_date
    current_year = datetime.now(TORONTO_TZ).year

    date_str = date_str.replace("Today, ", "").replace("Today", "").strip()
    date_str = re.sub(r"^\w{3},?\s*", "", date_str).strip()  # strip "Sat, "

    for fmt in ["%b %d", "%B %d", "%b %d %Y", "%B %d %Y"]:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.replace(year=current_year).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str!r}")


# ── Job 2: Send digests ───────────────────────────────────────────────────────

def send_digests(frequency: str = "daily"):
    """
    frequency: 'daily' or 'weekly'
    Fetches subscribers due for a digest, builds per-cinema movie lists,
    sends email, updates last_sent.
    """
    log.info(f"=== Starting {frequency} digest send ===")
    db = get_db()
    today = date.today()
    window_start = (today - timedelta(days=7)).isoformat() if frequency == "weekly" else today.isoformat()
    window_end = today.isoformat()

    # Fetch due subscribers
    query = db.table("subscribers").select("*").eq("frequency", frequency).eq("confirmed", True)
    subscribers = query.execute().data or []
    log.info(f"  {len(subscribers)} {frequency} subscribers")

    for sub in subscribers:
        # Skip if sent recently
        if sub.get("last_sent"):
            last = datetime.fromisoformat(sub["last_sent"]).date()
            if frequency == "daily" and last >= today:
                continue
            if frequency == "weekly" and (today - last).days < 6:
                continue

        cinema_slugs = sub.get("cinemas", [])

        # Fetch movies for this subscriber's cinemas with upcoming showtimes
        movies_by_cinema: dict[str, list] = {}
        for slug in cinema_slugs:
            # Get movies with showtimes in the window
            result = db.table("movies").select(
                "*, showtimes!inner(show_date,show_time,ticket_url)"
            ).eq("cinema_slug", slug).gte(
                "showtimes.show_date", window_start
            ).lte(
                "showtimes.show_date", window_end
            ).execute()

            from scrapers.base import Movie, Showtime
            cinema_movies = []
            for row in (result.data or []):
                m = Movie(
                    title=row["title"],
                    director=row.get("director") or "",
                    runtime=row.get("runtime") or "",
                    year=row.get("year") or "",
                    language=row.get("language") or "",
                    description=row.get("description") or "",
                    poster_url=row.get("poster_url") or "",
                    letterboxd_rating=row.get("letterboxd_rating"),
                    letterboxd_url=row.get("letterboxd_url") or "",
                    cinema=slug,
                    cinema_url="",
                    showtimes=[
                        Showtime(
                            date=st["show_date"],
                            time=st["show_time"],
                            ticket_url=st.get("ticket_url") or "",
                        )
                        for st in row.get("showtimes", [])
                    ],
                )
                cinema_movies.append(m)

            if cinema_movies:
                # Get display name from cinemas table
                cinema_info = db.table("cinemas").select("name,url").eq("slug", slug).execute().data
                display_name = cinema_info[0]["name"] if cinema_info else slug
                cinema_url = cinema_info[0]["url"] if cinema_info else ""
                for m in cinema_movies:
                    m.cinema_url = cinema_url
                movies_by_cinema[display_name] = cinema_movies

        if not any(movies_by_cinema.values()):
            log.info(f"  No movies for {sub['email']} — skipping")
            continue

        ctx = EmailContext(
            subscriber_email=sub["email"],
            unsubscribe_token=sub["token"],
            movies_by_cinema=movies_by_cinema,
            frequency=frequency,
            base_url=BASE_URL,
        )

        try:
            send_digest(ctx)
            db.table("subscribers").update({
                "last_sent": datetime.now(TORONTO_TZ).isoformat()
            }).eq("id", sub["id"]).execute()
            db.table("email_log").insert({
                "subscriber_id": sub["id"],
                "movie_count": sum(len(v) for v in movies_by_cinema.values()),
                "status": "sent",
            }).execute()
            log.info(f"  ✓ Sent to {sub['email']}")
        except Exception as e:
            log.error(f"  ✗ Failed to send to {sub['email']}: {e}")

    log.info(f"=== {frequency} digest done ===")


# ── Scheduler setup ───────────────────────────────────────────────────────────

def run_scheduler():
    scheduler = BlockingScheduler(timezone=TORONTO_TZ)

    # Scrape every day at 8:00 AM Toronto time
    scheduler.add_job(scrape_all_cinemas, "cron", hour=8, minute=0)

    # Daily digest at 9:00 AM
    scheduler.add_job(send_digests, "cron", hour=9, minute=0, kwargs={"frequency": "daily"})

    # Weekly digest every Friday at 9:00 AM
    scheduler.add_job(send_digests, "cron", day_of_week="fri", hour=9, minute=0, kwargs={"frequency": "weekly"})

    log.info("Scheduler started. Jobs: scrape@8AM, daily-digest@9AM, weekly-digest@Fri9AM (Toronto)")
    scheduler.start()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "scrape":
            scrape_all_cinemas()
        elif cmd == "daily":
            send_digests("daily")
        elif cmd == "weekly":
            send_digests("weekly")
        else:
            print("Usage: python3 -m scheduler.jobs [scrape|daily|weekly]")
    else:
        run_scheduler()
