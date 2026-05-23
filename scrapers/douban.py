"""
Douban rating fetcher via Douban search.
Also extracts Chinese title and Douban URL.
"""

import re
import time
from playwright.sync_api import sync_playwright


def fetch_douban_rating(title: str, year: str = "") -> tuple:
    """
    Returns (rating, douban_url, chinese_title) or (None, "", "").
    Rating is on Douban's 0-10 scale.
    """
    search_url = f"https://www.douban.com/search?cat=1002&q={title.replace(' ', '+')}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            locale="zh-CN",
        )
        page = context.new_page()
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)
            text = page.inner_text("body")
            html = page.content()
        except Exception as e:
            print(f"[Douban] Failed for '{title}': {e}")
            browser.close()
            return None, "", ""
        browser.close()

    # Split by [电影] markers
    blocks = re.split(r"\[电影\]", text)

    for block in blocks[1:]:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            continue

        # First non-empty line is the Chinese title (strip trailing noise like "可播放")
        chinese_title = re.sub(r"\s*(可播放|免费|会员|HD|4K).*$", "", lines[0]).strip()

        # Extract rating
        rating_m = re.search(r"(\d+\.\d+)\s*[\(（]\d+人评价", block)
        if not rating_m:
            continue
        rating = float(rating_m.group(1))

        # Year check with ±1 tolerance
        if year:
            year_m = re.search(r"\b(\d{4})\b", block)
            if year_m and abs(int(year_m.group(1)) - int(year)) > 1:
                continue

        # Extract Douban URL
        from urllib.parse import unquote

        url_m = re.search(r'url=(https[^&"]+subject[^&"]*)', html)
        douban_url = unquote(url_m.group(1)).split('"')[0] if url_m else ""

        return rating, douban_url, chinese_title

    print(f"[Douban] No match for '{title}'")
    return None, "", ""


def enrich_movies_with_douban(movies: list, delay: float = 2.0) -> list:
    """Add Douban ratings + Chinese title to Movie objects in-place."""
    for movie in movies:
        rating, url, cn_title = fetch_douban_rating(movie.title, movie.year)
        movie.douban_rating = rating
        movie.douban_url = url
        movie.douban_title = cn_title
        time.sleep(delay)
    return movies


if __name__ == "__main__":
    test_cases = [
        ("Midsommar", "2019"),
        ("Beau Travail", "2000"),
        ("Sansho the Bailiff", "1954"),
        ("Adaptation.", "2002"),
        ("Titane", "2021"),
    ]
    for title, year in test_cases:
        rating, url, cn = fetch_douban_rating(title, year)
        print(
            f"{title}: {f'{rating}/10' if rating else 'N/A'} | 中文名: {cn or 'N/A'} | {url}"
        )
        time.sleep(2)
