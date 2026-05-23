"""
Letterboxd rating fetcher.
Constructs slug from title, fetches film page via Playwright,
extracts rating from meta twitter:data2.
No API key needed.
"""

import re
import time
from playwright.sync_api import sync_playwright


def _title_to_slug(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[''']", "", s)  # remove apostrophes
    s = re.sub(r"[^a-z0-9\s-]", " ", s)  # non-alphanumeric -> space
    s = re.sub(r"\s+", "-", s.strip())  # spaces -> hyphens
    s = re.sub(r"-+", "-", s)  # collapse multiple hyphens
    return s.strip("-")


def _fetch_rating(slug: str, browser) -> float | None:
    """Fetch rating from letterboxd.com/film/{slug}/"""
    url = f"https://letterboxd.com/film/{slug}/"
    try:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Check we got a real film page, not 404
        if page.url != url and "letterboxd.com/film/" not in page.url:
            page.close()
            return None

        content = page.content()
        page.close()

        m = re.search(r'name="twitter:data2"\s+content="([\d.]+)\s+out of', content)
        if m:
            return float(m.group(1))
        return None
    except Exception:
        return None


def fetch_letterboxd_rating(title: str, year: str = "") -> tuple:
    """
    Returns (rating, letterboxd_url) or (None, "").
    Tries multiple slug variations.
    """
    base_slug = _title_to_slug(title)
    # Also try normalized title (strip series labels, director's cut etc.)
    clean = re.sub(
        r":?\s*(director.?s\s*cut|anniversary.*|sneak preview.*|\d+k\s+restoration.*)",
        "",
        title,
        flags=re.I,
    )
    clean_slug = _title_to_slug(clean.strip())

    candidates = []
    for slug in dict.fromkeys([base_slug, clean_slug]):  # deduplicate
        candidates.append(slug)
        if year:
            candidates.append(f"{slug}-{year}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            locale="en-US",
        )
        browser_ctx = context

        for slug in candidates:
            url = f"https://letterboxd.com/film/{slug}/"
            try:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=12000)
                content = page.content()
                page.close()

                # Check for 404 / not found
                if "Page Not Found" in content or "Sorry, we can't find" in content:
                    continue

                m = re.search(
                    r'name="twitter:data2"\s+content="([\d.]+)\s+out of', content
                )
                if m:
                    rating = float(m.group(1))
                    browser_ctx.close()
                    return rating, url

            except Exception:
                continue

        browser_ctx.close()

    print(f"[Letterboxd] No rating found for '{title}'")
    return None, ""


def enrich_movies_with_ratings(movies: list, delay: float = 1.0) -> list:
    """Add Letterboxd ratings to a list of Movie objects in-place."""
    for movie in movies:
        rating, url = fetch_letterboxd_rating(movie.title, movie.year)
        movie.letterboxd_rating = rating
        movie.letterboxd_url = url
        time.sleep(delay)
    return movies


if __name__ == "__main__":
    test_cases = [
        ("Midsommar", "2019"),
        ("Beau Travail", "2000"),
        ("Sansho the Bailiff", "1954"),
        ("Adaptation.", "2002"),
        ("Midsommar: Director's Cut!", "2019"),
    ]
    for title, year in test_cases:
        rating, url = fetch_letterboxd_rating(title, year)
        stars = f"{rating:.2f}/5" if rating else "N/A"
        print(f"{title}: {stars} — {url}")
