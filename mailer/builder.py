"""
Email HTML builder.
Produces a styled newsletter digest with movie cards,
Letterboxd + Douban ratings, poster, and showtimes.
"""

from dataclasses import dataclass
from typing import Optional
from scrapers.base import Movie


@dataclass
class EmailContext:
    subscriber_email: str
    unsubscribe_token: str
    movies_by_cinema: dict[str, list[Movie]]
    frequency: str
    base_url: str = "https://your-domain.com"


def _lb_stars(rating: Optional[float]) -> str:
    if rating is None:
        return ""
    full = int(rating)
    half = 1 if (rating - full) >= 0.25 else 0
    empty = 5 - full - half
    return "★" * full + ("½" if half else "") + "☆" * empty


def _format_showtimes(movie: Movie) -> str:
    by_date: dict[str, list] = {}
    for s in movie.showtimes:
        by_date.setdefault(s.date, []).append(s)

    rows = []
    for date, times in by_date.items():
        time_links = []
        for s in times:
            if s.ticket_url and s.ticket_url != "#":
                time_links.append(
                    f'<a href="{s.ticket_url}" style="color:#e8c547;text-decoration:none;">{s.time}</a>'
                )
            else:
                time_links.append(f'<span style="color:#555;">{s.time}</span>')
        rows.append(
            f"<tr>"
            f'<td style="color:#666;font-size:11px;padding:3px 12px 3px 0;white-space:nowrap;">{date}</td>'
            f'<td style="font-size:13px;padding:3px 0;">{" &nbsp;·&nbsp; ".join(time_links)}</td>'
            f"</tr>"
        )
    return f'<table style="border-collapse:collapse;margin-top:8px;">{"".join(rows)}</table>'


def build_movie_card(movie: Movie) -> str:
    # ── Ratings row ──────────────────────────────────────────────────────
    ratings_parts = []

    if movie.letterboxd_rating is not None:
        stars = _lb_stars(movie.letterboxd_rating)
        lb_open = (
            f'<a href="{movie.letterboxd_url}" style="color:inherit;text-decoration:none;">'
            if movie.letterboxd_url
            else ""
        )
        lb_close = "</a>" if movie.letterboxd_url else ""
        ratings_parts.append(
            f'{lb_open}<span style="color:#e8c547;letter-spacing:1px;">{stars}</span>'
            f' <span style="color:#888;font-size:11px;">LB {movie.letterboxd_rating:.2f}</span>{lb_close}'
        )

    if movie.douban_rating is not None:
        db_open = (
            f'<a href="{movie.douban_url}" style="color:inherit;text-decoration:none;">'
            if movie.douban_url
            else ""
        )
        db_close = "</a>" if movie.douban_url else ""
        ratings_parts.append(
            f'{db_open}<span style="color:#aaa;font-size:11px;">豆瓣 {movie.douban_rating:.1f}</span>{db_close}'
        )

    ratings_html = ""
    if ratings_parts:
        ratings_html = (
            f'<div style="margin:5px 0 8px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
            f'{"".join(ratings_parts)}'
            f"</div>"
        )

    # ── Meta line ─────────────────────────────────────────────────────────
    meta_parts = []
    if movie.director:
        meta_parts.append(f"dir. {movie.director}")
    if movie.year:
        meta_parts.append(movie.year)
    if movie.runtime:
        meta_parts.append(movie.runtime)
    if movie.language and movie.language.lower() not in ("english", ""):
        meta_parts.append(movie.language)
    meta_line = " &nbsp;·&nbsp; ".join(meta_parts)

    # ── Chinese title ─────────────────────────────────────────────────────
    cn_title_html = ""
    if getattr(movie, "douban_title", "") and movie.douban_title:
        cn_title_html = f'<span style="color:#666;font-size:13px;margin-left:8px;">{movie.douban_title}</span>'

    # ── Poster ────────────────────────────────────────────────────────────
    poster_html = ""
    if movie.poster_url:
        poster_html = (
            f'<a href="{movie.cinema_url}" style="display:block;flex-shrink:0;">'
            f'<img src="{movie.poster_url}" alt="{movie.title}" '
            f'style="width:80px;height:120px;object-fit:cover;border-radius:3px;display:block;" />'
            f"</a>"
        )

    # ── Description ───────────────────────────────────────────────────────
    description_html = ""
    if movie.description:
        desc = movie.description[:200] + ("…" if len(movie.description) > 200 else "")
        description_html = f'<p style="color:#888;font-size:12px;line-height:1.6;margin:6px 0 0;">{desc}</p>'

    showtimes_html = _format_showtimes(movie)

    return f"""
<div style="display:flex;gap:14px;padding:18px 0;border-bottom:1px solid #232323;">
  {f'<div>{poster_html}</div>' if poster_html else ""}
  <div style="flex:1;min-width:0;">
    <div style="display:flex;align-items:baseline;flex-wrap:wrap;gap:4px;margin-bottom:3px;">
      <h3 style="margin:0;font-size:16px;font-weight:600;color:#f0ece3;
                 font-family:'Playfair Display',Georgia,serif;line-height:1.3;">{movie.title}</h3>
      {cn_title_html}
    </div>
    <p style="margin:0 0 2px;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.7px;">{meta_line}</p>
    {ratings_html}
    {description_html}
    {showtimes_html}
  </div>
</div>"""


def build_cinema_section(cinema_name: str, cinema_url: str, movies: list[Movie]) -> str:
    cards = "".join(build_movie_card(m) for m in movies)
    return f"""
<div style="margin-bottom:36px;">
  <div style="border-left:3px solid #e8c547;padding-left:12px;margin-bottom:2px;">
    <a href="{cinema_url}" style="color:#e8c547;text-decoration:none;font-size:10px;
       text-transform:uppercase;letter-spacing:2.5px;font-weight:600;">{cinema_name}</a>
  </div>
  {cards}
</div>"""


def build_email_html(ctx: EmailContext) -> str:
    frequency_label = "Today's" if ctx.frequency == "daily" else "This Week's"

    cinema_sections = ""
    total_movies = 0
    for cinema_name, movies in ctx.movies_by_cinema.items():
        if not movies:
            continue
        cinema_url = movies[0].cinema_url if movies else "#"
        cinema_sections += build_cinema_section(cinema_name, cinema_url, movies)
        total_movies += len(movies)

    if not cinema_sections:
        cinema_sections = '<p style="color:#555;text-align:center;padding:40px 0;">No screenings found this period.</p>'

    unsubscribe_url = f"{ctx.base_url}/unsubscribe?token={ctx.unsubscribe_token}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{frequency_label} Toronto Cinema Digest</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
</head>
<body style="margin:0;padding:0;background:#111;font-family:'DM Sans',Helvetica,Arial,sans-serif;color:#f0ece3;">

<div style="max-width:620px;margin:0 auto;background:#161616;">

  <!-- Header -->
  <div style="padding:36px 40px 24px;border-bottom:1px solid #222;text-align:center;">
    <p style="margin:0 0 6px;font-size:9px;letter-spacing:4px;color:#555;text-transform:uppercase;">Toronto Independent Cinema</p>
    <h1 style="margin:0;font-family:'Playfair Display',Georgia,serif;font-size:26px;
               font-weight:400;color:#f0ece3;letter-spacing:-0.5px;">
      {frequency_label} Screenings
    </h1>
    <p style="margin:8px 0 0;font-size:11px;color:#444;">{total_movies} film{'s' if total_movies != 1 else ''} across your selected cinemas</p>
  </div>

  <!-- Body -->
  <div style="padding:28px 40px;">
    {cinema_sections}
  </div>

  <!-- Footer -->
  <div style="padding:20px 40px;border-top:1px solid #1e1e1e;text-align:center;">
    <p style="margin:0 0 6px;font-size:10px;color:#383838;">
      You're receiving this because you subscribed at toronto-cinema.com
    </p>
    <p style="margin:0;font-size:10px;color:#383838;">
      <a href="{unsubscribe_url}" style="color:#555;text-decoration:underline;">Unsubscribe</a>
      &nbsp;·&nbsp;
      <a href="{ctx.base_url}" style="color:#555;text-decoration:underline;">Manage preferences</a>
    </p>
  </div>

</div>
</body>
</html>"""


if __name__ == "__main__":
    from scrapers.base import Showtime

    fake_movies = [
        Movie(
            title="Beau Travail",
            director="Claire Denis",
            runtime="93 min",
            year="2000",
            language="French",
            description="A French Foreign Legion officer reflects on his time in Djibouti, and his disturbing relationship with a soldier he pushed to the breaking point.",
            poster_url="https://a.ltrbxd.com/resized/film-poster/5/1/9/6/5/51965-beau-travail-0-230-0-345-crop.jpg",
            letterboxd_rating=4.12,
            letterboxd_url="https://letterboxd.com/film/beau-travail/",
            douban_rating=7.5,
            douban_url="https://movie.douban.com/subject/1306791/",
            douban_title="军中禁恋",
            showtimes=[
                Showtime(
                    date="Tue, Jun 9",
                    time="6:30 PM",
                    ticket_url="https://paradiseonbloor.com/purchase/516438/",
                ),
            ],
            cinema="Paradise on Bloor",
            cinema_url="https://paradiseonbloor.com/coming-soon/",
        ),
        Movie(
            title="Titane",
            director="Julia Ducournau",
            runtime="108 min",
            year="2021",
            language="French",
            description="A woman with a metal plate in her head from a childhood car accident embarks on a bizarre journey.",
            poster_url="https://a.ltrbxd.com/resized/film-poster/4/9/8/1/4/498142-titane-0-230-0-345-crop.jpg",
            letterboxd_rating=3.54,
            letterboxd_url="https://letterboxd.com/film/titane/",
            douban_rating=6.4,
            douban_url="https://movie.douban.com/subject/34820925/",
            douban_title="钛",
            showtimes=[
                Showtime(
                    date="Wed, Jun 10",
                    time="8:30 PM",
                    ticket_url="https://paradiseonbloor.com/purchase/516440/",
                ),
                Showtime(
                    date="Thu, Jun 11",
                    time="6:00 PM",
                    ticket_url="https://paradiseonbloor.com/purchase/516441/",
                ),
            ],
            cinema="Paradise on Bloor",
            cinema_url="https://paradiseonbloor.com/coming-soon/",
        ),
    ]

    ctx = EmailContext(
        subscriber_email="test@example.com",
        unsubscribe_token="abc123",
        movies_by_cinema={"Paradise on Bloor": fake_movies},
        frequency="weekly",
    )
    html = build_email_html(ctx)
    with open("email_preview.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Preview written to email_preview.html")
    print(f"Email size: {len(html):,} chars")
