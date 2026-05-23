-- Toronto Cinema Mailer — Supabase Schema
-- Run this in your Supabase SQL editor

-- ── Subscribers ──────────────────────────────────────────────────────────────
create table if not exists subscribers (
  id          uuid primary key default gen_random_uuid(),
  email       text not null unique,
  frequency   text not null check (frequency in ('daily', 'weekly')),  -- 'daily' or 'weekly'
  cinemas     text[] not null default '{}',   -- e.g. ['paradise', 'revue', 'carlton', 'fox', 'tiff']
  token       text not null unique default encode(gen_random_bytes(32), 'hex'),  -- unsubscribe token
  confirmed   boolean not null default false,  -- double opt-in
  created_at  timestamptz not null default now(),
  last_sent   timestamptz
);

-- ── Cinema registry ──────────────────────────────────────────────────────────
create table if not exists cinemas (
  slug        text primary key,  -- 'paradise', 'revue', 'carlton', 'fox', 'tiff'
  name        text not null,
  url         text not null,
  scraper     text not null,     -- scraper class name
  active      boolean not null default true
);

insert into cinemas (slug, name, url, scraper) values
  ('paradise',       'Paradise on Bloor',              'https://paradiseonbloor.com/coming-soon/',                          'ParadiseScraper'),
  ('revue',          'Revue Cinema',                   'https://revuecinema.ca/films/',                                     'RevueScraper'),
  ('carlton',        'Imagine Cinemas Carlton',        'https://imaginecinemas.com/cinema/carlton/',                        'CarltonScraper'),
  ('fox',            'Fox Theatre',                    'https://www.foxtheatre.ca/whats-on/now-showing/',                   'CinemaClockScraper'),
  ('tiff',           'TIFF Lightbox',                  'https://www.tiff.net/calendar',                                    'CinemaClockScraper'),
  ('yonge-dundas',   'Cineplex Yonge Dundas & VIP',   'https://www.cineplex.com/Theatre/cineplex-cinemas-yonge-dundas-and-vip', 'CinemaClockScraper'),
  ('scotiabank',     'Scotiabank Theatre',             'https://www.cineplex.com/Theatre/scotiabank-theatre-toronto',       'CinemaClockScraper'),
  ('innis',          'Innis Town Hall',                'https://innis.utoronto.ca/film/',                                   'CinemaClockScraper'),
  ('hot-docs',       'Hot Docs Ted Rogers Cinema',     'https://www.hotdocs.ca/',                                          'CinemaClockScraper'),
  ('yonge-eglinton', 'Cineplex Yonge-Eglinton & VIP', 'https://www.cineplex.com/Theatre/cineplex-cinemas-yongeeglinton-and-vip', 'CinemaClockScraper'),
  ('empress-walk',   'Cineplex Empress Walk',          'https://www.cineplex.com/Theatre/cineplex-cinemas-empress-walk',   'CinemaClockScraper')
on conflict (slug) do nothing;

-- ── Scraped movies cache ──────────────────────────────────────────────────────
create table if not exists movies (
  id               uuid primary key default gen_random_uuid(),
  cinema_slug      text not null references cinemas(slug),
  title            text not null,
  director         text,
  runtime          text,
  year             text,
  language         text,
  description      text,
  poster_url       text,
  letterboxd_rating  numeric(3,2),
  letterboxd_url   text,
  scraped_at       timestamptz not null default now(),
  unique (cinema_slug, title)  -- dedup per cinema
);

-- ── Showtimes ─────────────────────────────────────────────────────────────────
create table if not exists showtimes (
  id          uuid primary key default gen_random_uuid(),
  movie_id    uuid not null references movies(id) on delete cascade,
  show_date   date not null,
  show_time   text not null,
  ticket_url  text,
  unique (movie_id, show_date, show_time)
);

-- ── Email log (avoid duplicate sends) ────────────────────────────────────────
create table if not exists email_log (
  id              uuid primary key default gen_random_uuid(),
  subscriber_id   uuid not null references subscribers(id) on delete cascade,
  sent_at         timestamptz not null default now(),
  movie_count     int,
  status          text default 'sent'
);

-- ── RLS policies (lock down to service role only) ────────────────────────────
alter table subscribers     enable row level security;
alter table movies          enable row level security;
alter table showtimes       enable row level security;
alter table email_log       enable row level security;

-- Service role bypasses RLS — your backend uses the service key, so this is fine.
-- Public (anon) role: only allow subscribing (insert) and unsubscribing (update via token)
create policy "anon can subscribe" on subscribers
  for insert to anon with check (true);

create policy "anon can confirm/unsubscribe by token" on subscribers
  for update to anon
  using (token = current_setting('app.token', true));

-- ── Indexes ───────────────────────────────────────────────────────────────────
create index if not exists idx_movies_cinema     on movies(cinema_slug);
create index if not exists idx_movies_scraped    on movies(scraped_at);
create index if not exists idx_showtimes_date    on showtimes(show_date);
create index if not exists idx_subscribers_freq  on subscribers(frequency, last_sent);
