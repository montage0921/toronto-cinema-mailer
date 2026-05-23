from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(locale="en-CA", timezone_id="America/Toronto")
    page = context.new_page()
    page.goto(
        "https://www.cinemaclock.com/movie-theaters/tiff-bell-lightbox",
        wait_until="networkidle",
        timeout=30000,
    )
    page.wait_for_timeout(2000)
    text = page.inner_text("body")
    browser.close()

# Print lines 1-150 to see the structure
lines = [l.strip() for l in text.splitlines() if l.strip()]
for i, l in enumerate(lines[:150]):
    print(f"{i:3d}: {repr(l)}")
