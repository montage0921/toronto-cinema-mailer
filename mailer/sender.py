"""
Email sender using Resend API.
https://resend.com — free tier: 3,000 emails/month, 100/day
"""

import os
import resend
from mailer.builder import build_email_html, EmailContext


def _init_resend():
    from dotenv import load_dotenv

    load_dotenv()
    resend.api_key = os.environ.get("RESEND_API_KEY", "")


FROM_ADDRESS = os.environ.get("FROM_EMAIL", "Toronto Cinema <digest@your-domain.com>")
REPLY_TO = os.environ.get("REPLY_TO_EMAIL", "")


def send_digest(ctx: EmailContext) -> dict:
    """Send a digest email to one subscriber. Returns Resend response."""
    frequency_label = "Today's" if ctx.frequency == "daily" else "This Week's"
    subject = f"🎬 {frequency_label} Toronto Cinema Screenings"

    html = build_email_html(ctx)

    params = {
        "from": FROM_ADDRESS,
        "to": [ctx.subscriber_email],
        "subject": subject,
        "html": html,
    }
    if REPLY_TO:
        params["reply_to"] = REPLY_TO

    response = resend.Emails.send(params)
    return response


def send_confirmation(email: str, token: str, base_url: str) -> dict:
    """Send double opt-in confirmation email."""
    confirm_url = f"{base_url}/confirm?token={token}"
    html = f"""<!DOCTYPE html>
<html><body style="background:#111;color:#f0ece3;font-family:Helvetica,Arial,sans-serif;padding:40px;">
<div style="max-width:500px;margin:0 auto;">
  <h2 style="font-family:Georgia,serif;color:#e8c547;">Confirm your subscription</h2>
  <p style="color:#aaa;line-height:1.6;">
    You signed up for the Toronto Cinema Digest. Click below to confirm your email address and start receiving screenings.
  </p>
  <a href="{confirm_url}"
     style="display:inline-block;margin:20px 0;padding:12px 28px;background:#e8c547;
            color:#111;font-weight:600;text-decoration:none;border-radius:4px;">
    Confirm subscription
  </a>
  <p style="color:#555;font-size:12px;">If you didn't sign up, ignore this email.</p>
</div>
</body></html>"""

    return resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [email],
            "subject": "Confirm your Toronto Cinema Digest subscription",
            "html": html,
        }
    )
