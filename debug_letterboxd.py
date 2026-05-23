from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
    page = context.new_page()
    page.goto(
        "https://letterboxd.com/search/films/Beau+Travail/",
        wait_until="load",
        timeout=20000,
    )
    # Wait for results to appear
    try:
        page.wait_for_selector("ul.results, .film-list, [data-film-slug]", timeout=8000)
    except:
        pass
    page.wait_for_timeout(2000)
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "html.parser")

print("=== /film/ links ===")
for a in soup.find_all("a", href=True):
    if "/film/" in a["href"] and "/films/" not in a["href"]:
        print(f"  {a['href']}  |  {repr(a.get_text().strip()[:40])}")

text = soup.get_text(" ")
idx = text.find("Beau")
print(
    f"\nText around Beau: {repr(text[max(0,idx-20):idx+300]) if idx>=0 else 'NOT FOUND'}"
)
print(f"\nPage size: {len(html)} bytes")
