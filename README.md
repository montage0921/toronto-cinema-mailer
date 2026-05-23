# Toronto Cinema Mailer — Backend

Scrapes 5 Toronto independent cinemas, fetches Letterboxd ratings,
and sends beautiful HTML digest emails to subscribers.

## Cinemas
- Paradise on Bloor
- Revue Cinema
- Imagine Cinemas Carlton
- Fox Theatre (Playwright)
- TIFF (Playwright)

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Environment variables
```bash
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY, BASE_URL
```

### 3. Database
Run `db/schema.sql` in your Supabase SQL editor.

### 4. Test scrapers locally
```bash
# Test any scraper directly
python3 -m scrapers.paradise
python3 -m scrapers.revue
python3 -m scrapers.carlton
python3 -m scrapers.fox      # requires Playwright
python3 -m scrapers.tiff     # requires Playwright

# Test Letterboxd ratings
python3 -m scrapers.letterboxd
```

### 5. Run the API
```bash
uvicorn api.main:app --reload --port 8000
```

### 6. Manual job triggers
```bash
python3 -m scheduler.jobs scrape    # run scrape now
python3 -m scheduler.jobs daily     # send daily digests now
python3 -m scheduler.jobs weekly    # send weekly digests now
```

### 7. Start scheduler (production)
```bash
python3 -m scheduler.jobs
```

## Adding a cinema / film festival
When you give me a new URL, I'll write a scraper class in `scrapers/`
and add it to the `SCRAPERS` dict in `scheduler/jobs.py`.
Then run `INSERT INTO cinemas ...` to register it.

## Architecture
```
scheduler/jobs.py
    ├── scrape_all_cinemas()    8AM daily
    │       ├── scrapers/*.py   → Movie objects
    │       ├── letterboxd.py   → add ratings
    │       └── supabase        → upsert movies + showtimes
    └── send_digests()          9AM daily / Fri weekly
            ├── supabase        → fetch subscribers + movies
            ├── email/builder.py → HTML email
            └── email/sender.py  → Resend API
```

## Deploy (Railway)
1. Connect your GitHub repo
2. Set env vars in Railway dashboard
3. Set start command: `python3 -m scheduler.jobs`
4. Add a separate Railway service for the API: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
