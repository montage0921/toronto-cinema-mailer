# Toronto Cinema Mailer — Project Structure

toronto-cinema-mailer/
├── scrapers/
│   ├── base.py              # Abstract base scraper class
│   ├── paradise.py          # Paradise on Bloor (requests+BS4)
│   ├── revue.py             # Revue Cinema (requests+BS4, JS pagination)
│   ├── carlton.py           # Imagine Cinemas Carlton (requests+BS4)
│   ├── fox.py               # Fox Theatre (Playwright)
│   ├── tiff.py              # TIFF (Playwright)
│   └── letterboxd.py        # Letterboxd rating fetcher
├── email/
│   ├── builder.py           # HTML email template builder
│   └── sender.py            # Resend API sender
├── scheduler/
│   └── jobs.py              # APScheduler cron jobs
├── api/
│   └── main.py              # FastAPI: subscribe/unsubscribe endpoints
├── frontend/                # Next.js subscription page (separate repo)
├── db/
│   └── schema.sql           # Supabase schema
├── requirements.txt
└── .env.example
